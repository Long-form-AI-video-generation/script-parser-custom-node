import json
import os
import time

import numpy as np
import pytest

from comfyui_script_to_video_suite.s2v_nodes import s2v_generation_metrics_node as metrics


def _checkerboard(size=32):
    y, x = np.indices((size, size))
    pattern = ((x // 4 + y // 4) % 2).astype(np.float32)
    return np.stack((pattern, 1.0 - pattern, pattern * 0.5), axis=2)


def _identity_drop_batch():
    anchor = _checkerboard()
    unrelated = np.roll(1.0 - anchor, 3, axis=1)
    return np.stack(
        (
            anchor,
            anchor,
            unrelated,
            unrelated,
            anchor,
            anchor,
            unrelated,
            unrelated,
        ),
        axis=0,
    )


def test_image_metrics_detect_section_keyframe_loss():
    images = _identity_drop_batch()

    result = metrics.analyze_image_batch(
        images,
        fps=4.0,
        frames_per_section=4,
        max_analysis_frames=32,
        identity_reference=images[:1],
    )

    assert result["metadata"]["frame_count"] == 8
    assert result["metadata"]["video_duration_seconds"] == 2.0
    assert result["sections"]["section_count"] == 2
    assert result["sections"]["average_keyframe_retention_at_frame_2"] < 0.45
    assert result["temporal"]["frozen_pair_fraction"] > 0.0
    assert result["visual_reference"]["enabled"] is True
    assert result["visual_reference"]["timeline"][0]["ssim"] == pytest.approx(1.0)
    assert result["technical_quality"]["average_sharpness_laplacian_variance"] > 0.0


def test_analysis_sampling_preserves_first_and_last_frames():
    indices = metrics.select_analysis_indices(
        total_frames=1000,
        max_frames=32,
        frames_per_section=33,
    )

    assert len(indices) <= 32
    assert indices[0] == 0
    assert indices[-1] == 999
    assert indices == sorted(set(indices))


def test_live_session_report_saves_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "folder_paths", None)
    monkeypatch.setenv("S2V_OUTPUT_DIR", str(tmp_path))
    images = _identity_drop_batch()

    value, session = metrics.GenerationMetricsStart_S2V().start(
        "generation dependency",
        enabled=True,
        session_name="identity test",
        sample_interval=0.1,
    )
    assert value == "generation dependency"
    time.sleep(0.12)

    response = metrics.GenerationMetricsReport_S2V().analyze(
        session,
        images,
        generation_folder="run_01",
        report_name="identity_metrics",
        save_report=True,
        fps=4.0,
        frames_per_section=4,
        max_analysis_frames=32,
        identity_reference=images[:1],
        prompt_context="Isaac enters the cockpit.",
    )

    returned = response["result"]
    report_path = returned[3]
    assert returned[0] is images
    assert returned[4] >= 0.1
    assert report_path.endswith(".md")
    assert os.path.isfile(report_path)
    assert os.path.isfile(report_path[:-3] + ".json")
    assert os.path.commonpath((str(tmp_path), report_path)) == str(tmp_path)

    report = json.loads(returned[2])
    assert report["schema_version"] == 1
    assert report["session"]["name"] == "identity test"
    assert report["memory"]["sample_count"] >= 2
    assert report["output"]["metadata"]["frame_count"] == 8
    assert any(item["code"] == "keyframe_loss" for item in report["observations"])
    assert report["prompt_context"] == "Isaac enters the cockpit."


def test_disabled_metrics_do_not_write_report(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "folder_paths", None)
    monkeypatch.setenv("S2V_OUTPUT_DIR", str(tmp_path))
    images = np.zeros((2, 8, 8, 3), dtype=np.float32)
    _, session = metrics.GenerationMetricsStart_S2V().start(
        "value", enabled=False, session_name="disabled", sample_interval=0.5
    )

    response = metrics.GenerationMetricsReport_S2V().analyze(
        session,
        images,
        generation_folder="disabled_run",
        save_report=True,
    )

    assert "disabled" in response["result"][1].lower()
    assert response["result"][3] == ""
    assert not (tmp_path / "disabled_run").exists()


@pytest.mark.parametrize("folder", ["", "/absolute", "../escape", "C:\\absolute"])
def test_metrics_folder_rejects_unsafe_paths(folder):
    with pytest.raises(ValueError):
        metrics._clean_relative_folder(folder)


def test_memory_summary_aggregates_process_and_multiple_gpus():
    samples = [
        {
            "elapsed_seconds": 0.0,
            "process_rss_bytes": 100,
            "system_available_bytes": 1000,
            "cgroup": {
                "enabled": True,
                "current_bytes": 400,
                "peak_bytes": 450,
                "limit_bytes": 1000,
                "events": {"oom": 0, "oom_kill": 0},
            },
            "gpus": [
                {
                    "index": 0,
                    "name": "GPU 0",
                    "total_bytes": 1000,
                    "allocated_bytes": 200,
                    "reserved_bytes": 300,
                    "device_used_bytes": 350,
                }
            ],
        },
        {
            "elapsed_seconds": 1.0,
            "process_rss_bytes": 250,
            "system_available_bytes": 800,
            "cgroup": {
                "enabled": True,
                "current_bytes": 900,
                "peak_bytes": 920,
                "limit_bytes": 1000,
                "events": {"oom": 1, "oom_kill": 0},
            },
            "gpus": [
                {
                    "index": 0,
                    "name": "GPU 0",
                    "total_bytes": 1000,
                    "allocated_bytes": 600,
                    "reserved_bytes": 700,
                    "device_used_bytes": 800,
                },
                {
                    "index": 1,
                    "name": "GPU 1",
                    "total_bytes": 2000,
                    "allocated_bytes": 400,
                    "reserved_bytes": 500,
                    "device_used_bytes": 650,
                },
            ],
        },
    ]

    result = metrics.summarize_memory(samples)

    assert result["process_rss_peak_bytes"] == 250
    assert result["process_rss_peak_increase_bytes"] == 150
    assert result["minimum_system_available_bytes"] == 800
    assert result["peak_gpu_allocated_bytes"] == 600
    assert result["peak_gpu_device_used_bytes"] == 800
    assert result["cgroup"]["peak_bytes"] == 920
    assert result["cgroup"]["peak_utilization_fraction"] == pytest.approx(0.92)
    assert result["cgroup"]["events_delta"]["oom"] == 1
    assert len(result["gpus"]) == 2


def test_cgroup_reader_matches_available_v2_files():
    sample = metrics._cgroup_memory()

    assert isinstance(sample["enabled"], bool)
    assert sample["current_bytes"] >= 0
    assert sample["limit_bytes"] >= 0
    assert isinstance(sample["events"], dict)
