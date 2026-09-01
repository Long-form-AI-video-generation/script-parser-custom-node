# KR 5.3 Generation Metrics

The metrics feature uses two connected nodes because a node that runs only after video
generation cannot know when generation started or sample peak memory while it was running.

## Nodes

### Metrics: Start Measurement (S2V)

Place this node inline immediately before the first expensive generation stage.

- `value` is a wildcard pass-through. Connect an existing prompt, prompt list, model, or
  other value that the generation path already requires.
- `enabled` controls the whole metrics session. When disabled, no sampler thread or report
  files are created.
- `sample_interval` controls RAM and VRAM polling. `0.5` seconds is the recommended default.
- `metrics_session` must be connected to the report node.

The pass-through connection is important. It guarantees that the start node executes before
the sampler instead of running as an unrelated parallel branch.

### Metrics: Analyze and Save Report (S2V)

Connect this node after the final accumulated image batch.

- `images` receives the complete final frame batch before or alongside the final video saver.
- `metrics_session` receives the session from the start node.
- `generation_folder` should receive `root_folder` from the Generation Output Folder node.
- `frames_per_section` should match the workflow section length, for example `33`. Set it to
  `0` when the batch is not section based.
- `identity_reference` is optional. Connect the canonical character anchor or first approved
  keyframe to measure global visual drift from that image.
- `prompt_context` is optional traceability data. It is stored in the JSON but is not sent to
  an LLM.

The report node is an output node, so it runs even when none of its outputs are connected.
Its `images` output is an unchanged pass-through and can be used by later nodes.

## Recommended Wiring

```text
prompt/list/model
  -> Metrics Start.value
  -> existing generation input

Metrics Start.metrics_session
  -> Metrics Report.metrics_session

final accumulated IMAGE batch
  -> Metrics Report.images

Generation Output Folder.root_folder
  -> Metrics Report.generation_folder

optional canonical character anchor
  -> Metrics Report.identity_reference
```

## Saved Artifacts

Reports are saved under:

```text
ComfyUI/output/<generation_folder>/metrics/
```

Each run writes:

- `generation_metrics_<timestamp>_<session>.json`: full machine-readable data and timelines.
- `generation_metrics_<timestamp>_<session>.md`: compact human-readable analysis.

Writes are atomic so an interrupted write does not leave a partially valid report.

## Metrics

### Performance

- Generation wall time from the inline start node to the report node.
- Generated frames per second.
- Process RAM at start/end, sampled peak RAM, and peak increase.
- Minimum available system RAM.
- Linux cgroup memory usage, limit, peak utilization, and OOM/OOM-kill events. This is the
  relevant limit when Jupyter or a container has less RAM than the host machine.
- Per-GPU sampled allocated, reserved, and total device-used VRAM.
- Analysis time, reported separately from generation time.

### Technical Image Quality

- Brightness, contrast, saturation, and black/white clipping.
- Laplacian variance as a no-reference sharpness proxy.
- Per-frame values and aggregate values.

### Temporal Consistency

- Blockwise structural similarity (SSIM) between adjacent analyzed frames.
- Mean absolute pixel change as a motion proxy.
- Brightness flicker and color drift.
- Frozen-pair and abrupt-change fractions.

### Section and Character-Anchor Behavior

- Similarity between the first frame of each section and frames `+1`, `+2`, `+4`, and `+8`.
  This directly exposes the failure where a correct keyframe disappears immediately.
- Similarity across section boundaries.
- Optional similarity to a supplied canonical reference image using blockwise SSIM and color
  histogram cosine similarity.

## Interpretation

These metrics are intended for comparing workflow revisions under the same resolution,
prompts, models, seeds, and section settings. They are not a substitute for human review.

- Low keyframe retention can indicate weak I2V start-image conditioning.
- Very high frozen-pair rate can indicate insufficient motion.
- Low temporal SSIM can indicate flicker, identity changes, or intended fast motion.
- Low boundary SSIM is expected for deliberate hard cuts.
- Reference-image similarity measures the whole image. It is not face recognition and can fall
  when camera framing or background changes even if the character remains correct.
- Periodic memory sampling can miss allocations shorter than the configured interval.
- A cgroup limit shown as `0 B` means no finite cgroup v2 limit was available to the node.
