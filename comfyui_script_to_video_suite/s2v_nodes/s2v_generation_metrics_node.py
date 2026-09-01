from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import threading
import time
import uuid

import numpy as np

try:
    import torch
except Exception:
    torch = None

try:
    import folder_paths
except ImportError:
    folder_paths = None

from .s2v_progress_node import any_type


REPORT_SCHEMA_VERSION = 1
BYTES_PER_GIB = 1024 ** 3
MAX_SESSION_SECONDS = 12 * 60 * 60


class MetricsSession:
    """Live, low-overhead process and CUDA memory sampler."""

    def __init__(self, enabled=True, session_name="generation", sample_interval=0.5):
        self.enabled = bool(enabled)
        self.session_id = uuid.uuid4().hex[:12]
        self.session_name = _clean_label(session_name, "generation")
        self.sample_interval = max(0.1, float(sample_interval))
        self.started_perf = time.perf_counter()
        self.started_utc = _utc_now()
        self.stopped_perf = None
        self.stopped_utc = None
        self.samples = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

        if self.enabled:
            self._record_sample()
            self._thread = threading.Thread(
                target=self._sample_until_stopped,
                name=f"s2v-metrics-{self.session_id}",
                daemon=True,
            )
            self._thread.start()

    def _sample_until_stopped(self):
        while not self._stop_event.wait(self.sample_interval):
            self._record_sample()
            if time.perf_counter() - self.started_perf >= MAX_SESSION_SECONDS:
                self._stop_event.set()
                break

    def _record_sample(self):
        sample = _memory_sample(time.perf_counter() - self.started_perf)
        with self._lock:
            self.samples.append(sample)

    def stop(self):
        if self.stopped_perf is None:
            self.stopped_perf = time.perf_counter()
            self.stopped_utc = _utc_now()
            self._stop_event.set()
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=max(1.0, self.sample_interval * 2.0))
            if self.enabled:
                self._record_sample()
        return self.snapshot()

    def snapshot(self):
        stopped_perf = self.stopped_perf or time.perf_counter()
        with self._lock:
            samples = list(self.samples)
        return {
            "id": self.session_id,
            "name": self.session_name,
            "enabled": self.enabled,
            "started_at_utc": self.started_utc,
            "stopped_at_utc": self.stopped_utc,
            "elapsed_seconds": max(0.0, stopped_perf - self.started_perf),
            "sample_interval_seconds": self.sample_interval,
            "samples": samples,
        }


class GenerationMetricsStart_S2V:
    """Start metrics before generation while passing an inline value through."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (any_type,),
                "enabled": ("BOOLEAN", {"default": True}),
                "session_name": (
                    "STRING",
                    {
                        "default": "generation",
                        "multiline": False,
                        "tooltip": "Readable name stored in the metrics report.",
                    },
                ),
                "sample_interval": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.1,
                        "max": 10.0,
                        "step": 0.1,
                        "tooltip": "Seconds between RAM/VRAM samples. 0.5 is a low-overhead default.",
                    },
                ),
            }
        }

    @classmethod
    def IS_CHANGED(cls, **_kwargs):
        return float("NaN")

    RETURN_TYPES = (any_type, "S2V_METRICS_SESSION")
    RETURN_NAMES = ("value", "metrics_session")
    FUNCTION = "start"
    CATEGORY = "Script To Video Suite/Metrics"

    def start(self, value, enabled=True, session_name="generation", sample_interval=0.5):
        session = MetricsSession(enabled, session_name, sample_interval)
        if session.enabled:
            print(
                f"[S2V Metrics] Started '{session.session_name}' "
                f"({session.session_id}), sampling every {session.sample_interval:.1f}s.",
                flush=True,
            )
        else:
            print("[S2V Metrics] Measurement disabled; value passed through.", flush=True)
        return (value, session)


class GenerationMetricsReport_S2V:
    """Stop a metrics session, analyze generated frames, and save reports."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "metrics_session": ("S2V_METRICS_SESSION", {"forceInput": True}),
                "images": ("IMAGE", {"forceInput": True}),
                "generation_folder": (
                    "STRING",
                    {
                        "default": "generation",
                        "multiline": False,
                        "tooltip": "Relative folder under ComfyUI/output. Reports go in its metrics subfolder.",
                    },
                ),
                "report_name": (
                    "STRING",
                    {"default": "generation_metrics", "multiline": False},
                ),
                "save_report": ("BOOLEAN", {"default": True}),
                "fps": ("FLOAT", {"default": 16.0, "min": 0.01, "max": 240.0, "step": 0.01}),
                "frames_per_section": (
                    "INT",
                    {
                        "default": 33,
                        "min": 0,
                        "max": 10000,
                        "step": 1,
                        "tooltip": "Set to 0 to disable section-boundary and keyframe-retention analysis.",
                    },
                ),
                "max_analysis_frames": (
                    "INT",
                    {
                        "default": 256,
                        "min": 16,
                        "max": 2048,
                        "step": 16,
                        "tooltip": "Maximum frames sampled for pixel analysis. Timing and frame count remain exact.",
                    },
                ),
            },
            "optional": {
                "identity_reference": (
                    "IMAGE",
                    {
                        "forceInput": True,
                        "tooltip": "Optional canonical character/keyframe image for visual-reference similarity.",
                    },
                ),
                "prompt_context": (
                    "STRING",
                    {
                        "forceInput": True,
                        "multiline": True,
                        "tooltip": "Optional prompt or prompt JSON stored with the report for traceability.",
                    },
                ),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **_kwargs):
        return float("NaN")

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING", "FLOAT", "FLOAT", "FLOAT")
    RETURN_NAMES = (
        "images",
        "report_summary",
        "report_json",
        "report_path",
        "generation_seconds",
        "peak_vram_gb",
        "temporal_consistency",
    )
    FUNCTION = "analyze"
    CATEGORY = "Script To Video Suite/Metrics"
    OUTPUT_NODE = True

    def analyze(
        self,
        metrics_session,
        images,
        generation_folder="generation",
        report_name="generation_metrics",
        save_report=True,
        fps=16.0,
        frames_per_section=33,
        max_analysis_frames=256,
        identity_reference=None,
        prompt_context="",
    ):
        if not isinstance(metrics_session, MetricsSession):
            raise TypeError("metrics_session must come from the S2V Metrics Start node.")

        session = metrics_session.stop()
        elapsed = float(session["elapsed_seconds"])
        if not session["enabled"]:
            summary = "S2V generation metrics are disabled. No report was saved."
            return _result(
                images,
                summary,
                json.dumps({"enabled": False}, indent=2),
                "",
                elapsed,
                0.0,
                0.0,
            )

        analysis_started = time.perf_counter()
        errors = []
        try:
            image_metrics = analyze_image_batch(
                images,
                fps=float(fps),
                frames_per_section=max(0, int(frames_per_section)),
                max_analysis_frames=max(16, int(max_analysis_frames)),
                identity_reference=identity_reference,
            )
        except Exception as exc:
            errors.append(f"Image analysis failed: {exc}")
            image_metrics = _empty_image_metrics(images, float(fps))

        memory = summarize_memory(session["samples"])
        frame_count = int(image_metrics["metadata"]["frame_count"])
        throughput = frame_count / elapsed if elapsed > 0 else 0.0
        analysis_seconds = time.perf_counter() - analysis_started

        report = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "created_at_utc": _utc_now(),
            "session": {key: value for key, value in session.items() if key != "samples"},
            "timing": {
                "generation_seconds": elapsed,
                "analysis_seconds": analysis_seconds,
                "generated_frames_per_second": throughput,
                "video_duration_seconds": image_metrics["metadata"]["video_duration_seconds"],
            },
            "memory": memory,
            "output": image_metrics,
            "prompt_context": str(prompt_context or ""),
            "observations": [],
            "errors": errors,
            "limitations": [
                "Pixel SSIM and reference similarity are visual proxies, not semantic or face-identity recognition.",
                "RAM and VRAM are sampled periodically, so allocations shorter than the sample interval may be missed.",
                "Scene cuts naturally lower temporal similarity; interpret boundary metrics with the shot plan.",
                "No-reference sharpness and exposure metrics do not measure storytelling or prompt alignment.",
            ],
        }
        report["observations"] = build_observations(report)

        report_path = ""
        if save_report:
            try:
                report_path = save_metrics_report(report, generation_folder, report_name)
            except Exception as exc:
                error = f"Saving metrics report failed: {exc}"
                report["errors"].append(error)
                print(f"[S2V Metrics] {error}", flush=True)

        report_json = json.dumps(report, indent=2, ensure_ascii=True)
        summary = build_console_summary(report, report_path)
        print(summary, flush=True)

        peak_vram_bytes = memory.get("peak_gpu_device_used_bytes", 0) or memory.get(
            "peak_gpu_allocated_bytes", 0
        )
        peak_vram = float(peak_vram_bytes) / BYTES_PER_GIB
        temporal_consistency = float(
            image_metrics.get("temporal", {}).get("average_adjacent_ssim", 0.0)
        )
        return _result(
            images,
            summary,
            report_json,
            report_path,
            elapsed,
            peak_vram,
            temporal_consistency,
        )


def analyze_image_batch(images, fps=16.0, frames_per_section=33, max_analysis_frames=256, identity_reference=None):
    total_frames = _frame_count(images)
    if total_frames <= 0:
        raise ValueError("The generated image batch is empty.")

    first_full = _frame_to_numpy(_frame_at(images, 0))
    height, width, channels = first_full.shape
    indices = select_analysis_indices(total_frames, max_analysis_frames, frames_per_section)
    frames = {index: _resize_for_analysis(_frame_to_numpy(_frame_at(images, index))) for index in indices}

    per_frame = []
    for index in indices:
        frame = frames[index]
        gray = _to_gray(frame)
        per_frame.append(
            {
                "frame": index,
                "brightness": float(np.mean(gray)),
                "contrast": float(np.std(gray)),
                "saturation": float(np.mean(np.max(frame, axis=2) - np.min(frame, axis=2))),
                "black_clipping_fraction": float(np.mean(frame <= 0.01)),
                "white_clipping_fraction": float(np.mean(frame >= 0.99)),
                "sharpness_laplacian_variance": _laplacian_variance(gray),
            }
        )

    temporal_pairs = []
    for left_index, right_index in zip(indices, indices[1:]):
        left = frames[left_index]
        right = frames[right_index]
        temporal_pairs.append(
            {
                "from_frame": left_index,
                "to_frame": right_index,
                "frame_gap": right_index - left_index,
                "ssim": block_ssim(left, right),
                "mean_absolute_difference": float(np.mean(np.abs(left - right))),
                "brightness_change": abs(float(np.mean(_to_gray(left))) - float(np.mean(_to_gray(right)))),
                "color_drift": float(np.mean(np.abs(np.mean(left, axis=(0, 1)) - np.mean(right, axis=(0, 1))))),
            }
        )

    exact_pairs = [pair for pair in temporal_pairs if pair["frame_gap"] == 1]
    summary_pairs = exact_pairs or temporal_pairs
    temporal = {
        "average_adjacent_ssim": _mean(pair["ssim"] for pair in summary_pairs),
        "minimum_adjacent_ssim": _min(pair["ssim"] for pair in summary_pairs),
        "average_motion_mae": _mean(pair["mean_absolute_difference"] for pair in summary_pairs),
        "average_brightness_change": _mean(pair["brightness_change"] for pair in summary_pairs),
        "average_color_drift": _mean(pair["color_drift"] for pair in summary_pairs),
        "frozen_pair_fraction": _fraction(
            pair["ssim"] >= 0.995 and pair["mean_absolute_difference"] <= 0.005
            for pair in summary_pairs
        ),
        "abrupt_change_fraction": _fraction(pair["ssim"] < 0.35 for pair in summary_pairs),
        "pair_count": len(summary_pairs),
        "timeline": temporal_pairs,
    }

    section_metrics = analyze_sections(frames, total_frames, frames_per_section)
    reference_metrics = analyze_reference(frames, identity_reference)
    quality = {
        "average_brightness": _mean(item["brightness"] for item in per_frame),
        "average_contrast": _mean(item["contrast"] for item in per_frame),
        "average_saturation": _mean(item["saturation"] for item in per_frame),
        "average_black_clipping_fraction": _mean(item["black_clipping_fraction"] for item in per_frame),
        "average_white_clipping_fraction": _mean(item["white_clipping_fraction"] for item in per_frame),
        "average_sharpness_laplacian_variance": _mean(
            item["sharpness_laplacian_variance"] for item in per_frame
        ),
        "per_frame": per_frame,
    }

    return {
        "metadata": {
            "frame_count": total_frames,
            "analyzed_frame_count": len(indices),
            "sampled_frame_indices": indices,
            "width": width,
            "height": height,
            "channels": channels,
            "fps": float(fps),
            "video_duration_seconds": total_frames / float(fps) if fps > 0 else 0.0,
        },
        "technical_quality": quality,
        "temporal": temporal,
        "sections": section_metrics,
        "visual_reference": reference_metrics,
    }


def select_analysis_indices(total_frames, max_frames, frames_per_section=0):
    total_frames = max(0, int(total_frames))
    max_frames = max(1, int(max_frames))
    if total_frames <= max_frames:
        return list(range(total_frames))

    priority = {0, total_frames - 1}
    if frames_per_section > 0:
        starts = list(range(0, total_frames, frames_per_section))
        max_sections = max(1, (max_frames - 2) // 5)
        if len(starts) > max_sections:
            chosen = np.linspace(0, len(starts) - 1, max_sections, dtype=int)
            starts = [starts[index] for index in sorted(set(chosen.tolist()))]
        for start in starts:
            end = min(total_frames - 1, start + frames_per_section - 1)
            for offset in (0, 1, 2, 4, 8):
                priority.add(min(end, start + offset))
            priority.add(end)

    if len(priority) > max_frames:
        ordered = sorted(priority)
        selected = np.linspace(0, len(ordered) - 1, max_frames, dtype=int)
        return sorted({ordered[index] for index in selected.tolist()})

    remaining = max_frames - len(priority)
    if remaining > 0:
        uniform = np.linspace(0, total_frames - 1, max_frames + 2, dtype=int)
        candidates = [index for index in uniform.tolist() if index not in priority]
        priority.update(candidates[:remaining])
    return sorted(priority)


def analyze_sections(frames, total_frames, frames_per_section):
    if frames_per_section <= 0:
        return {
            "enabled": False,
            "frames_per_section": 0,
            "section_count": 0,
            "average_keyframe_retention_at_frame_2": 0.0,
            "average_boundary_ssim": 0.0,
            "details": [],
            "boundaries": [],
        }

    details = []
    boundaries = []
    section_count = int(math.ceil(total_frames / frames_per_section))
    for section_index in range(section_count):
        start = section_index * frames_per_section
        end = min(total_frames - 1, start + frames_per_section - 1)
        if start not in frames:
            continue
        start_frame = frames[start]
        retention = {}
        for offset in (1, 2, 4, 8):
            target = min(end, start + offset)
            if target in frames and target != start:
                retention[str(offset)] = block_ssim(start_frame, frames[target])
        details.append(
            {
                "section": section_index + 1,
                "start_frame": start,
                "end_frame": end,
                "keyframe_retention_ssim": retention,
            }
        )

        if section_index > 0:
            previous_end = start - 1
            if previous_end in frames:
                boundaries.append(
                    {
                        "before_section": section_index,
                        "after_section": section_index + 1,
                        "from_frame": previous_end,
                        "to_frame": start,
                        "ssim": block_ssim(frames[previous_end], start_frame),
                        "mean_absolute_difference": float(
                            np.mean(np.abs(frames[previous_end] - start_frame))
                        ),
                    }
                )

    offset_two = [
        detail["keyframe_retention_ssim"]["2"]
        for detail in details
        if "2" in detail["keyframe_retention_ssim"]
    ]
    return {
        "enabled": True,
        "frames_per_section": frames_per_section,
        "section_count": section_count,
        "analyzed_section_count": len(details),
        "average_keyframe_retention_at_frame_2": _mean(offset_two),
        "minimum_keyframe_retention_at_frame_2": _min(offset_two),
        "average_boundary_ssim": _mean(item["ssim"] for item in boundaries),
        "details": details,
        "boundaries": boundaries,
    }


def analyze_reference(frames, identity_reference):
    if identity_reference is None:
        return {
            "enabled": False,
            "average_ssim": 0.0,
            "minimum_ssim": 0.0,
            "average_color_histogram_cosine": 0.0,
            "timeline": [],
        }

    reference = _resize_for_analysis(_frame_to_numpy(_frame_at(identity_reference, 0)))
    timeline = []
    for index, frame in frames.items():
        resized_reference = _resize_to_shape(reference, frame.shape[0], frame.shape[1])
        timeline.append(
            {
                "frame": index,
                "ssim": block_ssim(resized_reference, frame),
                "color_histogram_cosine": color_histogram_cosine(resized_reference, frame),
            }
        )
    return {
        "enabled": True,
        "average_ssim": _mean(item["ssim"] for item in timeline),
        "minimum_ssim": _min(item["ssim"] for item in timeline),
        "average_color_histogram_cosine": _mean(
            item["color_histogram_cosine"] for item in timeline
        ),
        "timeline": timeline,
    }


def block_ssim(left, right, blocks=8):
    left_gray = _to_gray(left).astype(np.float64, copy=False)
    right_gray = _to_gray(right).astype(np.float64, copy=False)
    if left_gray.shape != right_gray.shape:
        right_gray = _resize_to_shape(right, left_gray.shape[0], left_gray.shape[1])
        right_gray = _to_gray(right_gray).astype(np.float64, copy=False)

    height, width = left_gray.shape
    block_y = max(1, min(int(blocks), height))
    block_x = max(1, min(int(blocks), width))
    usable_height = max(block_y, (height // block_y) * block_y)
    usable_width = max(block_x, (width // block_x) * block_x)
    left_gray = left_gray[:usable_height, :usable_width]
    right_gray = right_gray[:usable_height, :usable_width]
    patch_height = usable_height // block_y
    patch_width = usable_width // block_x

    left_patches = left_gray.reshape(block_y, patch_height, block_x, patch_width)
    right_patches = right_gray.reshape(block_y, patch_height, block_x, patch_width)
    axes = (1, 3)
    left_mean = np.mean(left_patches, axis=axes)
    right_mean = np.mean(right_patches, axis=axes)
    left_var = np.var(left_patches, axis=axes)
    right_var = np.var(right_patches, axis=axes)
    covariance = np.mean(
        (left_patches - left_mean[:, None, :, None])
        * (right_patches - right_mean[:, None, :, None]),
        axis=axes,
    )

    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    numerator = (2 * left_mean * right_mean + c1) * (2 * covariance + c2)
    denominator = (left_mean ** 2 + right_mean ** 2 + c1) * (left_var + right_var + c2)
    score = np.mean(numerator / np.maximum(denominator, 1e-12))
    return float(np.clip(score, -1.0, 1.0))


def color_histogram_cosine(left, right, bins=16):
    left_hist = []
    right_hist = []
    for channel in range(3):
        left_hist.extend(np.histogram(left[:, :, channel], bins=bins, range=(0.0, 1.0))[0])
        right_hist.extend(np.histogram(right[:, :, channel], bins=bins, range=(0.0, 1.0))[0])
    left_hist = np.asarray(left_hist, dtype=np.float64)
    right_hist = np.asarray(right_hist, dtype=np.float64)
    denominator = np.linalg.norm(left_hist) * np.linalg.norm(right_hist)
    if denominator <= 0:
        return 0.0
    return float(np.dot(left_hist, right_hist) / denominator)


def summarize_memory(samples):
    if not samples:
        return {
            "sample_count": 0,
            "process_rss_start_bytes": 0,
            "process_rss_end_bytes": 0,
            "process_rss_peak_bytes": 0,
            "process_rss_peak_increase_bytes": 0,
            "minimum_system_available_bytes": 0,
            "cgroup": _empty_cgroup_summary(),
            "peak_gpu_allocated_bytes": 0,
            "peak_gpu_reserved_bytes": 0,
            "peak_gpu_device_used_bytes": 0,
            "gpus": [],
            "timeline": [],
        }

    rss = [int(item.get("process_rss_bytes", 0)) for item in samples]
    available = [int(item.get("system_available_bytes", 0)) for item in samples]
    gpu_indices = sorted(
        {
            int(gpu["index"])
            for sample in samples
            for gpu in sample.get("gpus", [])
        }
    )
    gpu_summaries = []
    for index in gpu_indices:
        values = [
            gpu
            for sample in samples
            for gpu in sample.get("gpus", [])
            if int(gpu["index"]) == index
        ]
        gpu_summaries.append(
            {
                "index": index,
                "name": next((item.get("name", "") for item in values if item.get("name")), ""),
                "total_bytes": max((int(item.get("total_bytes", 0)) for item in values), default=0),
                "peak_allocated_bytes": max(
                    (int(item.get("allocated_bytes", 0)) for item in values), default=0
                ),
                "peak_reserved_bytes": max(
                    (int(item.get("reserved_bytes", 0)) for item in values), default=0
                ),
                "peak_device_used_bytes": max(
                    (int(item.get("device_used_bytes", 0)) for item in values), default=0
                ),
            }
        )

    cgroup = summarize_cgroup_memory(samples)

    return {
        "sample_count": len(samples),
        "process_rss_start_bytes": rss[0],
        "process_rss_end_bytes": rss[-1],
        "process_rss_peak_bytes": max(rss),
        "process_rss_peak_increase_bytes": max(0, max(rss) - rss[0]),
        "minimum_system_available_bytes": min((value for value in available if value > 0), default=0),
        "cgroup": cgroup,
        "peak_gpu_allocated_bytes": max(
            (item["peak_allocated_bytes"] for item in gpu_summaries), default=0
        ),
        "peak_gpu_reserved_bytes": max(
            (item["peak_reserved_bytes"] for item in gpu_summaries), default=0
        ),
        "peak_gpu_device_used_bytes": max(
            (item["peak_device_used_bytes"] for item in gpu_summaries), default=0
        ),
        "gpus": gpu_summaries,
        "timeline": samples,
    }


def summarize_cgroup_memory(samples):
    values = [sample.get("cgroup", {}) for sample in samples]
    values = [value for value in values if value.get("enabled")]
    if not values:
        return _empty_cgroup_summary()

    current = [int(value.get("current_bytes", 0)) for value in values]
    reported_peaks = [int(value.get("peak_bytes", 0)) for value in values]
    limits = [int(value.get("limit_bytes", 0)) for value in values]
    limit = max((value for value in limits if value > 0), default=0)
    peak = max(current + reported_peaks)
    event_names = sorted(
        {
            name
            for value in values
            for name in value.get("events", {})
        }
    )
    first_events = values[0].get("events", {})
    last_events = values[-1].get("events", {})
    event_deltas = {
        name: max(0, int(last_events.get(name, 0)) - int(first_events.get(name, 0)))
        for name in event_names
    }
    return {
        "enabled": True,
        "current_start_bytes": current[0],
        "current_end_bytes": current[-1],
        "peak_bytes": peak,
        "limit_bytes": limit,
        "peak_utilization_fraction": peak / limit if limit > 0 else 0.0,
        "events_start": first_events,
        "events_end": last_events,
        "events_delta": event_deltas,
    }


def build_observations(report):
    observations = []
    quality = report["output"].get("technical_quality", {})
    temporal = report["output"].get("temporal", {})
    sections = report["output"].get("sections", {})
    reference = report["output"].get("visual_reference", {})
    memory = report.get("memory", {})

    def add(level, code, message):
        observations.append({"level": level, "code": code, "message": message})

    clipping = quality.get("average_black_clipping_fraction", 0) + quality.get(
        "average_white_clipping_fraction", 0
    )
    if clipping > 0.10:
        add("warning", "exposure_clipping", "More than 10% of sampled channel values are clipped.")
    elif clipping > 0.03:
        add("notice", "exposure_clipping", "Some black or white clipping is present in sampled frames.")

    if temporal.get("frozen_pair_fraction", 0) > 0.20:
        add("warning", "frozen_frames", "More than 20% of analyzed adjacent pairs are nearly identical.")
    if temporal.get("average_adjacent_ssim", 0) < 0.35 and temporal.get("pair_count", 0):
        add("warning", "temporal_instability", "Adjacent frames have low structural similarity.")
    if temporal.get("abrupt_change_fraction", 0) > 0.20:
        add("notice", "abrupt_changes", "Frequent abrupt visual changes were detected; compare them with intended cuts.")

    retention = sections.get("average_keyframe_retention_at_frame_2", 0)
    if sections.get("enabled") and retention and retention < 0.45:
        add(
            "warning",
            "keyframe_loss",
            "Section starts change strongly within two frames; start-image conditioning may be collapsing.",
        )

    if reference.get("enabled") and reference.get("average_ssim", 0) < 0.30:
        add(
            "notice",
            "reference_drift",
            "Output has low global visual similarity to the supplied reference; inspect identity manually.",
        )

    available = int(memory.get("minimum_system_available_bytes", 0))
    if available and available < 2 * BYTES_PER_GIB:
        add("warning", "low_system_memory", "Available system RAM dropped below 2 GiB.")

    cgroup = memory.get("cgroup", {})
    cgroup_utilization = float(cgroup.get("peak_utilization_fraction", 0))
    if cgroup_utilization > 0.90:
        add(
            "warning",
            "high_cgroup_memory_pressure",
            "The ComfyUI cgroup used more than 90% of its memory limit.",
        )
    elif cgroup_utilization > 0.80:
        add(
            "notice",
            "high_cgroup_memory_pressure",
            "The ComfyUI cgroup used more than 80% of its memory limit.",
        )
    cgroup_events = cgroup.get("events_delta", {})
    if int(cgroup_events.get("oom_kill", 0)) > 0:
        add(
            "warning",
            "cgroup_oom_kill",
            "The cgroup recorded an out-of-memory process kill during this generation.",
        )
    elif int(cgroup_events.get("oom", 0)) > 0:
        add(
            "warning",
            "cgroup_oom",
            "The cgroup recorded an out-of-memory event during this generation.",
        )

    for gpu in memory.get("gpus", []):
        total = int(gpu.get("total_bytes", 0))
        device_used = int(gpu.get("peak_device_used_bytes", 0))
        reserved = int(gpu.get("peak_reserved_bytes", 0))
        pressure = max(device_used, reserved)
        if total and pressure / total > 0.95:
            add(
                "warning",
                "high_vram_pressure",
                f"GPU {gpu['index']} used or reserved more than 95% of its reported VRAM.",
            )

    if not observations:
        add("info", "no_threshold_warnings", "No configured technical warning threshold was crossed.")
    return observations


def save_metrics_report(report, generation_folder, report_name):
    output_root = _output_root()
    relative_folder = _clean_relative_folder(generation_folder)
    report_directory = os.path.abspath(os.path.join(output_root, relative_folder, "metrics"))
    if os.path.commonpath((output_root, report_directory)) != output_root:
        raise ValueError("Metrics folder must remain inside the ComfyUI output folder.")
    os.makedirs(report_directory, exist_ok=True)

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(report_name or "generation_metrics")).strip("._")
    safe_name = safe_name or "generation_metrics"
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{safe_name}_{timestamp}_{report['session']['id']}"
    json_path = os.path.join(report_directory, f"{stem}.json")
    markdown_path = os.path.join(report_directory, f"{stem}.md")

    report["artifacts"] = {
        "json": json_path,
        "markdown": markdown_path,
    }
    _atomic_write(json_path, json.dumps(report, indent=2, ensure_ascii=True))
    _atomic_write(markdown_path, build_markdown_report(report))
    return markdown_path


def build_markdown_report(report):
    timing = report["timing"]
    memory = report["memory"]
    output = report["output"]
    metadata = output["metadata"]
    quality = output.get("technical_quality", {})
    temporal = output.get("temporal", {})
    sections = output.get("sections", {})
    reference = output.get("visual_reference", {})

    lines = [
        f"# Generation Metrics: {report['session']['name']}",
        "",
        f"Generated: `{report['created_at_utc']}`  ",
        f"Session: `{report['session']['id']}`",
        "",
        "## Timing",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Generation wall time | {timing['generation_seconds']:.2f} s |",
        f"| Generated frames | {metadata['frame_count']} |",
        f"| Video duration | {timing['video_duration_seconds']:.2f} s |",
        f"| Throughput | {timing['generated_frames_per_second']:.3f} frames/s |",
        f"| Metrics analysis time | {timing['analysis_seconds']:.2f} s |",
        "",
        "## Memory",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Peak process RSS | {_format_bytes(memory['process_rss_peak_bytes'])} |",
        f"| RSS increase during session | {_format_bytes(memory['process_rss_peak_increase_bytes'])} |",
        f"| Minimum available system RAM | {_format_bytes(memory['minimum_system_available_bytes'])} |",
        f"| Peak cgroup memory | {_format_bytes(memory['cgroup']['peak_bytes'])} |",
        f"| Cgroup memory limit | {_format_bytes(memory['cgroup']['limit_bytes'])} |",
        f"| Peak cgroup utilization | {memory['cgroup']['peak_utilization_fraction']:.2%} |",
        f"| Cgroup OOM events | {memory['cgroup']['events_delta'].get('oom', 0)} |",
        f"| Cgroup OOM kills | {memory['cgroup']['events_delta'].get('oom_kill', 0)} |",
        f"| Peak sampled CUDA allocation | {_format_bytes(memory['peak_gpu_allocated_bytes'])} |",
        f"| Peak sampled CUDA reservation | {_format_bytes(memory['peak_gpu_reserved_bytes'])} |",
        f"| Peak sampled device VRAM use | {_format_bytes(memory['peak_gpu_device_used_bytes'])} |",
        f"| Memory samples | {memory['sample_count']} |",
        "",
        "## Output Quality",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Resolution | {metadata['width']} x {metadata['height']} |",
        f"| Frames analyzed | {metadata['analyzed_frame_count']} / {metadata['frame_count']} |",
        f"| Average brightness | {quality.get('average_brightness', 0):.4f} |",
        f"| Average contrast | {quality.get('average_contrast', 0):.4f} |",
        f"| Average saturation | {quality.get('average_saturation', 0):.4f} |",
        f"| Average sharpness proxy | {quality.get('average_sharpness_laplacian_variance', 0):.6f} |",
        f"| Black clipping | {quality.get('average_black_clipping_fraction', 0):.2%} |",
        f"| White clipping | {quality.get('average_white_clipping_fraction', 0):.2%} |",
        "",
        "## Consistency",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Average adjacent SSIM | {temporal.get('average_adjacent_ssim', 0):.4f} |",
        f"| Minimum adjacent SSIM | {temporal.get('minimum_adjacent_ssim', 0):.4f} |",
        f"| Average motion MAE | {temporal.get('average_motion_mae', 0):.4f} |",
        f"| Frozen adjacent pairs | {temporal.get('frozen_pair_fraction', 0):.2%} |",
        f"| Abrupt adjacent changes | {temporal.get('abrupt_change_fraction', 0):.2%} |",
        f"| Average section-start retention at frame +2 | {sections.get('average_keyframe_retention_at_frame_2', 0):.4f} |",
        f"| Average section-boundary SSIM | {sections.get('average_boundary_ssim', 0):.4f} |",
        f"| Reference-image SSIM | {reference.get('average_ssim', 0):.4f} |",
        f"| Reference color-histogram similarity | {reference.get('average_color_histogram_cosine', 0):.4f} |",
        "",
        "## Observations",
        "",
    ]
    for observation in report.get("observations", []):
        lines.append(
            f"- **{observation['level'].upper()} - {observation['code']}**: {observation['message']}"
        )

    if sections.get("details"):
        lines.extend(
            [
                "",
                "## Section Keyframe Retention",
                "",
                "| Section | Start | End | +1 SSIM | +2 SSIM | +4 SSIM | +8 SSIM |",
                "|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for item in sections["details"]:
            values = item["keyframe_retention_ssim"]
            lines.append(
                f"| {item['section']} | {item['start_frame']} | {item['end_frame']} | "
                f"{_format_metric(values.get('1'))} | {_format_metric(values.get('2'))} | "
                f"{_format_metric(values.get('4'))} | {_format_metric(values.get('8'))} |"
            )

    if report.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])

    lines.extend(["", "## Interpretation Limits", ""])
    lines.extend(f"- {item}" for item in report.get("limitations", []))
    lines.append("")
    return "\n".join(lines)


def build_console_summary(report, report_path=""):
    timing = report["timing"]
    memory = report["memory"]
    output = report["output"]
    temporal = output.get("temporal", {})
    sections = output.get("sections", {})
    lines = [
        "[S2V Metrics] Generation analysis complete",
        f"  generation: {timing['generation_seconds']:.2f}s",
        f"  peak process RSS: {_format_bytes(memory['process_rss_peak_bytes'])}",
        f"  peak cgroup memory: {_format_bytes(memory['cgroup']['peak_bytes'])}",
        f"  peak sampled VRAM: {_format_bytes(memory['peak_gpu_device_used_bytes'])}",
        f"  temporal SSIM: {temporal.get('average_adjacent_ssim', 0):.4f}",
        f"  keyframe retention +2: {sections.get('average_keyframe_retention_at_frame_2', 0):.4f}",
    ]
    if report_path:
        lines.append(f"  report: {report_path}")
    if report.get("errors"):
        lines.append(f"  errors: {len(report['errors'])}")
    return "\n".join(lines)


def _result(images, summary, report_json, report_path, elapsed, peak_vram, consistency):
    return {
        "ui": {"text": [summary]},
        "result": (
            images,
            summary,
            report_json,
            report_path,
            float(elapsed),
            float(peak_vram),
            float(consistency),
        ),
    }


def _memory_sample(elapsed_seconds):
    system = _system_memory()
    return {
        "elapsed_seconds": float(elapsed_seconds),
        "process_rss_bytes": _process_rss_bytes(),
        "system_total_bytes": system.get("total", 0),
        "system_available_bytes": system.get("available", 0),
        "system_used_bytes": max(0, system.get("total", 0) - system.get("available", 0)),
        "cgroup": _cgroup_memory(),
        "gpus": _gpu_memory(),
    }


def _process_rss_bytes():
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as handle:
            resident_pages = int(handle.read().split()[1])
        return resident_pages * int(os.sysconf("SC_PAGE_SIZE"))
    except Exception:
        try:
            import resource

            value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            return value if os.uname().sysname == "Darwin" else value * 1024
        except Exception:
            return 0


def _system_memory():
    values = {}
    try:
        with open("/proc/meminfo", "r", encoding="ascii") as handle:
            for line in handle:
                key, raw = line.split(":", 1)
                values[key] = int(raw.strip().split()[0]) * 1024
    except Exception:
        return {"total": 0, "available": 0}
    return {
        "total": values.get("MemTotal", 0),
        "available": values.get("MemAvailable", values.get("MemFree", 0)),
    }


def _cgroup_memory():
    relative_path = ""
    try:
        with open("/proc/self/cgroup", "r", encoding="ascii") as handle:
            for line in handle:
                hierarchy, controllers, path = line.rstrip("\n").split(":", 2)
                if hierarchy == "0" and not controllers:
                    relative_path = path.lstrip("/")
                    break
    except Exception:
        return _empty_cgroup_sample()

    base = os.path.join("/sys/fs/cgroup", relative_path)
    current = _read_integer_file(os.path.join(base, "memory.current"))
    if current is None:
        return _empty_cgroup_sample()

    raw_limit = _read_text_file(os.path.join(base, "memory.max"))
    limit = 0 if raw_limit in (None, "max") else _parse_nonnegative_integer(raw_limit)
    peak = _read_integer_file(os.path.join(base, "memory.peak")) or 0
    events = {}
    raw_events = _read_text_file(os.path.join(base, "memory.events"))
    if raw_events:
        for line in raw_events.splitlines():
            fields = line.split()
            if len(fields) == 2:
                events[fields[0]] = _parse_nonnegative_integer(fields[1])
    return {
        "enabled": True,
        "current_bytes": current,
        "peak_bytes": peak,
        "limit_bytes": limit,
        "events": events,
    }


def _gpu_memory():
    if torch is None:
        return []
    try:
        if not torch.cuda.is_available():
            return []
        result = []
        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)
            device_free = 0
            device_used = 0
            try:
                device_free, reported_total = torch.cuda.mem_get_info(index)
                device_used = max(0, int(reported_total) - int(device_free))
            except Exception:
                pass
            result.append(
                {
                    "index": index,
                    "name": str(properties.name),
                    "total_bytes": int(properties.total_memory),
                    "allocated_bytes": int(torch.cuda.memory_allocated(index)),
                    "reserved_bytes": int(torch.cuda.memory_reserved(index)),
                    "device_free_bytes": int(device_free),
                    "device_used_bytes": int(device_used),
                }
            )
        return result
    except Exception:
        return []


def _frame_count(images):
    shape = getattr(images, "shape", None)
    if shape is not None:
        if len(shape) == 3:
            return 1
        if len(shape) >= 4:
            return int(shape[0])
    try:
        return len(images)
    except Exception:
        return 0


def _frame_at(images, index):
    shape = getattr(images, "shape", None)
    if shape is not None and len(shape) == 3:
        if index != 0:
            raise IndexError(index)
        return images
    return images[index]


def _frame_to_numpy(frame):
    if hasattr(frame, "detach"):
        frame = frame.detach()
    if hasattr(frame, "cpu"):
        frame = frame.cpu()
    if hasattr(frame, "float"):
        frame = frame.float()
    if hasattr(frame, "numpy"):
        frame = frame.numpy()
    array = np.asarray(frame)
    while array.ndim > 3 and array.shape[0] == 1:
        array = array[0]
    if array.ndim == 2:
        array = array[:, :, None]
    if array.ndim != 3:
        raise ValueError(f"Expected an HWC or CHW image, got shape {array.shape}.")
    if array.shape[0] in (1, 3, 4) and array.shape[-1] not in (1, 3, 4):
        array = np.transpose(array, (1, 2, 0))
    if array.shape[2] == 1:
        array = np.repeat(array, 3, axis=2)
    elif array.shape[2] >= 4:
        array = array[:, :, :3]
    if array.shape[2] != 3:
        raise ValueError(f"Expected 1, 3, or 4 channels, got shape {array.shape}.")
    array = array.astype(np.float32, copy=False)
    if array.size and float(np.nanmax(array)) > 1.5:
        array = array / 255.0
    return np.clip(np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0)


def _resize_for_analysis(frame, max_dimension=192):
    height, width = frame.shape[:2]
    if max(height, width) <= max_dimension:
        return frame
    scale = max_dimension / float(max(height, width))
    return _resize_to_shape(frame, max(1, round(height * scale)), max(1, round(width * scale)))


def _resize_to_shape(frame, target_height, target_width):
    height, width = frame.shape[:2]
    if height == target_height and width == target_width:
        return frame
    y_indices = np.linspace(0, height - 1, target_height).astype(np.int64)
    x_indices = np.linspace(0, width - 1, target_width).astype(np.int64)
    return frame[y_indices][:, x_indices]


def _to_gray(frame):
    return (
        frame[:, :, 0] * 0.2126
        + frame[:, :, 1] * 0.7152
        + frame[:, :, 2] * 0.0722
    )


def _laplacian_variance(gray):
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    center = gray[1:-1, 1:-1]
    laplacian = (
        gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
        - 4.0 * center
    )
    return float(np.var(laplacian))


def _output_root():
    if folder_paths is not None:
        root = folder_paths.get_output_directory()
    else:
        root = os.getenv("S2V_OUTPUT_DIR", os.path.join(os.getcwd(), "output"))
    return os.path.abspath(root)


def _clean_relative_folder(folder_name):
    value = str(folder_name or "").strip().replace("\\", "/")
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError("Generation folder must be a non-empty relative path.")
    parts = []
    for raw_part in value.split("/"):
        part = raw_part.strip()
        if not part or part == ".":
            continue
        if part == "..":
            raise ValueError("Generation folder cannot contain '..'.")
        part = re.sub(r"[^A-Za-z0-9._ -]+", "_", part).strip(" .")
        if not part:
            raise ValueError("Generation folder contains an invalid path component.")
        parts.append(part)
    if not parts:
        raise ValueError("Generation folder must contain at least one valid name.")
    return "/".join(parts)


def _atomic_write(path, text):
    temporary = f"{path}.tmp-{uuid.uuid4().hex}"
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _empty_image_metrics(images, fps):
    frame_count = _frame_count(images)
    return {
        "metadata": {
            "frame_count": frame_count,
            "analyzed_frame_count": 0,
            "sampled_frame_indices": [],
            "width": 0,
            "height": 0,
            "channels": 0,
            "fps": fps,
            "video_duration_seconds": frame_count / fps if fps > 0 else 0.0,
        },
        "technical_quality": {},
        "temporal": {},
        "sections": {},
        "visual_reference": {},
    }


def _clean_label(value, fallback):
    value = " ".join(str(value or "").split())
    return value[:200] or fallback


def _empty_cgroup_sample():
    return {
        "enabled": False,
        "current_bytes": 0,
        "peak_bytes": 0,
        "limit_bytes": 0,
        "events": {},
    }


def _empty_cgroup_summary():
    return {
        "enabled": False,
        "current_start_bytes": 0,
        "current_end_bytes": 0,
        "peak_bytes": 0,
        "limit_bytes": 0,
        "peak_utilization_fraction": 0.0,
        "events_start": {},
        "events_end": {},
        "events_delta": {},
    }


def _read_text_file(path):
    try:
        with open(path, "r", encoding="ascii") as handle:
            return handle.read().strip()
    except Exception:
        return None


def _read_integer_file(path):
    value = _read_text_file(path)
    if value is None or value == "max":
        return None
    return _parse_nonnegative_integer(value)


def _parse_nonnegative_integer(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _mean(values):
    values = list(values)
    return float(np.mean(values)) if values else 0.0


def _min(values):
    values = list(values)
    return float(np.min(values)) if values else 0.0


def _fraction(values):
    values = list(values)
    return float(sum(bool(value) for value in values) / len(values)) if values else 0.0


def _format_bytes(value):
    value = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TiB"


def _format_metric(value):
    return "n/a" if value is None else f"{float(value):.4f}"
