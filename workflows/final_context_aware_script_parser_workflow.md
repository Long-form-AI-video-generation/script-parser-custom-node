# Final Context-Aware Script Parser Workflow

API workflow file:

`workflows/final_context_aware_script_parser_workflow.json`

## Main Path

1. `115 PDFUploadChunker_S2V`
   Uploads/selects the PDF and chunks the script.

2. `116 StoryboardGenerator_S2V`
   Converts PDF chunks into storyboard panels.

3. `117 PromptGenerator_S2V`
   Converts storyboard panels into JSON with `image_prompt` and `video_prompt`.

4. `114 StringSwitch_S2V`
   Uses generated prompts by default. The old manual JSON remains as fallback if
   `use_manual` is set back to `True`.

5. `39 PromptUnpacker_S2V`
   Splits prompt JSON into image prompt and video prompt lists.

6. `41 PromptLoopBuilder_S2V`
   Statelessly exposes the first prompts and the full video prompt list for the
   single-run loop.

## Video Continuity Path

The first section uses prompt index `0`.

The loop starts at prompt index `1` and carries accumulated frames forward.

Inside each loop:

- `90` selects the current video prompt from the full list.
- `80 WanVideoContextSelector` selects context frames from accumulated frames.
- `89 WanVideoClipVisionEncode` encodes the selected context frames.
- `95`, `83`, and `84` generate and decode the next section.
- `94` appends the new section to the accumulated frame batch.
- `13` feeds accumulated frames back into the loop.

`118 context_frames` is set to `4` so the context selector is no longer limited
to the single last-frame value used by `21 motion_frames`.

## Outputs

- `57` saves the initial T2V seed output.
- `77` saves the first I2V section.
- `28` saves loop section/accumulated previews.
- `36` saves the final accumulated video after the loop.
- `58` and `74` are preview nodes for visual inspection.
