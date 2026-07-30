
import os
import re
from .gemini_relay_client import ask_gemini_via_relay
from . import llm_cache
from .s2v_progress_node import announce_to_ui

# One script "page" for panel-density purposes (matches the chunker's default chunk_size).
PAGE_CHARS = 4000
STORYBOARD_CACHE_VERSION = "wan-video-storyboard-v3-painted-color"

# This ensures the node functions even if the external .txt file is missing.
DEFAULT_STORYBOARD_PROMPT = (
    "You are an expert anime previz director preparing prompts for a Wan-style image-to-video "
    "model. Read the script chunk and convert it into a compact sequence of video-ready "
    "storyboard panels.\n\n"
    "The model understands concrete visual instructions best. Each panel must describe ONE "
    "continuous shot: one location, one main subject, one visible story beat, one camera idea, "
    "and one motion idea. Do not write literary summaries, motivations, or dialogue logic as "
    "the action.\n\n"
    "STYLE TARGET FOR EVERY PANEL:\n"
    "- Polished full-color hand-painted Japanese fantasy animation, classic Studio Ghibli-inspired "
    "storybook anime, rich opaque colors, lush gouache and watercolor backgrounds, "
    "soft natural light, expressive rounded characters, and delicate colored contours.\n"
    "- Every image is a finished theatrical-animation frame, never a sketch, monochrome "
    "drawing, line-art sheet, storyboard panel, or unfinished concept image.\n"
    "- Use positive anime descriptors only. Do not write realistic, live action, photo, "
    "cosplay, CGI, or 3D terms in the positive descriptions.\n\n"
    "PANEL RULES:\n"
    "1. Start each panel with a unique number: PANEL 001, PANEL 002, etc.\n"
    "2. A panel is a video section, not a screenplay paragraph. Merge small repeated actions "
    "into one clear beat, but never merge two different locations.\n"
    "3. Every panel must advance the story from the previous panel through a changed action, "
    "prop interaction, expression, camera framing, or location detail.\n"
    "4. Use canonical character names from the CAST SHEET. Never use pronouns or vague labels "
    "for named characters.\n"
    "5. Screenplay scene headings such as EXT., INT., INT./EXT., EXT./INT. or SCENE BOUNDARY "
    "markers are HARD CUTS. Start a new panel at every hard cut.\n"
    "6. Never blend locations across a hard cut. The new panel must describe only the new "
    "location unless the script explicitly says the previous location is visible.\n\n"
    "7. Mark TRANSITION as CONTINUE only when the next section should literally begin from the "
    "previous section's final frame in the same location. Otherwise use CUT.\n\n"
    "For EACH panel, use exactly these labels:\n"
    "- SCENE_ID: stable short ID reused only while location, time, and lighting remain the same.\n"
    "- TRANSITION: CUT or CONTINUE.\n"
    "- SHOT_TYPE: camera framing, e.g. ESTABLISHING SHOT, WIDE SHOT, MEDIUM SHOT, CLOSE UP, POV SHOT.\n"
    "- LOCATION: exact visible place for this one shot.\n"
    "- SUBJECT: main visible focus using canonical names.\n"
    "- CHARACTER_APPEARANCE: stable visual descriptors for every recurring visible character.\n"
    "- KEYFRAME_DESCRIPTION: a single still-frame description the image model can draw.\n"
    "- ACTION_DESCRIPTION: the visible story beat in this shot, written as physical action.\n"
    "- MOTION_DESCRIPTION: 1 short motion instruction for the video model.\n"
    "- CAMERA_MOTION: static, slow push-in, pan, tilt, tracking, handheld drift, etc.\n"
    "- CONTINUITY_ANCHORS: exact recurring props, outfit, lighting, and location details to preserve.\n"
    "- DIALOGUE: spoken line or visible phone/screen text if essential, otherwise NONE.\n\n"
    "Separate panels with --- PANEL BREAK --- on its own line. Output only the storyboard panels.\n"
)

SCENE_HEADING_RE = re.compile(
    r"(?im)^(?P<heading>\s*(?:INT\.?/EXT\.?|EXT\.?/INT\.?|I/E\.|E/I\.|INT\.|EXT\.|XT\.)[^\n]*)$"
)

def load_prompt_from_file() -> str:
    """
    Lazy loads text content from the local prompt file.
    Returns the file content if successful, otherwise returns the internal fallback.
    """
    filename = "storyboard_master_prompt.txt"
    current_dir = os.path.dirname(__file__)
    file_path = os.path.join(current_dir, filename)
    
    if not os.path.exists(file_path):
        print(f"S2V Warning: {filename} not found. Using internal fallback prompt.")
        return DEFAULT_STORYBOARD_PROMPT
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"S2V Warning: Could not read {filename}. Reason: {e}. Using internal fallback.")
        return DEFAULT_STORYBOARD_PROMPT

class StoryboardGenerator:
    """
    A custom node that iterates through script chunks, calls an LLM to generate
    storyboard panels for each, and then combines and de-duplicates the results.
    """
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        """
        Defines the input widgets for the node.
        - chunks: The list of text chunks from the PDFChunker.
        - master_prompt: A multi-line text field pre-filled with the lazy-loaded prompt.
        """
        return {
            "required": {
                "chunks": ("CHUNKS",),
                "master_prompt": ("STRING", {
                    "default": load_prompt_from_file(),
                    "multiline": True
                }),
            },
            "optional": {
                "shots_per_page": ("INT", {
                    "default": 0, "min": 0, "max": 50, "step": 1,
                    "tooltip": "Panel density: shots to generate per page of script "
                               "(a page is counted as 4000 characters). 0 = let the LLM decide. "
                               "Each chunk gets a budget proportional to its length, so the whole "
                               "script is always covered end to end.",
                }),
                "bible_text": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Connect the Character Extractor's bible_text. The cast sheet is "
                               "shown to the LLM for EVERY chunk, so characters keep their "
                               "canonical names and looks across the whole script.",
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("storyboard_text",)
    FUNCTION = "generate_storyboard"
    CATEGORY = "Script To Video Suite"

    @staticmethod
    def _annotate_scene_boundaries(text: str) -> str:
        """Make screenplay scene changes unambiguous for the storyboard LLM."""
        def repl(match):
            heading = match.group("heading").strip()
            return f"\nSCENE BOUNDARY - HARD CUT TO: {heading}\n{heading}"

        return SCENE_HEADING_RE.sub(repl, text or "")

    @staticmethod
    def _minimum_panel_budget_for_chunk(text: str) -> int:
        scene_heading_count = len(SCENE_HEADING_RE.findall(text or ""))
        return max(1, scene_heading_count)

    @staticmethod
    def _select_representative_panels(panels: list[str], max_panels: int) -> list[str]:
        """Emergency fallback cap that preserves beginning/middle/end coverage."""
        if max_panels <= 0 or len(panels) <= max_panels:
            return panels
        if max_panels == 1:
            return [panels[len(panels) // 2]]

        last_index = len(panels) - 1
        selected_indices = [
            round(i * last_index / (max_panels - 1))
            for i in range(max_panels)
        ]
        return [panels[i] for i in selected_indices]

    def _condense_panels_to_budget(self, panels: list[str], max_panels: int) -> list[str] | None:
        if max_panels <= 0 or len(panels) <= max_panels:
            return panels

        panel_delimiter = "--- PANEL BREAK ---"
        source_storyboard = f"\n\n{panel_delimiter}\n\n".join(panels)
        prompt = (
            "You are a senior anime storyboard editor. The draft storyboard below has too many panels.\n\n"
            f"Rewrite it into AT MOST {max_panels} final storyboard panels. Do not select random panels; "
            "combine and rewrite the most important beats into a coherent mini-story that represents the "
            "whole source script from beginning to end.\n\n"
            "Rules:\n"
            "- Preserve continuity across the selected beats: beginning, middle, and ending should make sense together.\n"
            "- Preserve every major hard location cut if possible. Do not blend exterior and interior locations into one image.\n"
            "- If a panel combines several beats, write a single clear visual frame that implies those beats without overlays.\n"
            "- Keep named characters by canonical name.\n"
            "- Output ONLY storyboard panels using the full master format, including SCENE_ID, "
            "TRANSITION, LOCATION, SHOT_TYPE, SUBJECT, KEYFRAME_DESCRIPTION, "
            "ACTION_DESCRIPTION, MOTION_DESCRIPTION, CAMERA_MOTION, CONTINUITY_ANCHORS, and DIALOGUE.\n"
            "- Separate panels with --- PANEL BREAK ---.\n\n"
            f"Draft storyboard:\n{source_storyboard}"
        )

        for attempt in range(2):
            response_text = ask_gemini_via_relay(prompt)
            if response_text.startswith("Error:"):
                print(f"Storyboard budget condensation attempt {attempt + 1} failed: {response_text}")
                continue

            condensed = self._split_unique_panels(response_text)
            if condensed and len(condensed) <= max_panels:
                print(f"Condensed storyboard to {len(condensed)} coherent panel(s) with the LLM budget editor.")
                return condensed

            if condensed:
                print(
                    f"Storyboard budget editor returned {len(condensed)} panels "
                    f"for max_panels={max_panels}; retrying once."
                )

        return None

    @staticmethod
    def _split_unique_panels(raw_text: str) -> list[str]:
        panel_delimiter = "--- PANEL BREAK ---"
        all_panels_raw = re.split(r'\s*--- PANEL BREAK ---\s*|(?=\bPANEL\s+\d+)', raw_text)

        final_panels = []
        seen_panels = set()

        for panel_block in all_panels_raw:
            panel_block = panel_block.strip()
            if not panel_block:
                continue

            if panel_block not in seen_panels:
                final_panels.append(panel_block)
                seen_panels.add(panel_block)

        return final_panels

    def _post_process_storyboard(self, raw_text: str, max_panels: int = 0) -> str:
        """Helper function to clean up, de-duplicate and cap storyboard panels."""
        panel_delimiter = "--- PANEL BREAK ---"
        final_panels = self._split_unique_panels(raw_text)

        print(f"De-duplication complete. Kept {len(final_panels)} unique panels.")

        if max_panels > 0 and len(final_panels) > max_panels:
            print(
                f"Storyboard over budget: {len(final_panels)} panels for max_panels={max_panels}. "
                "Asking the LLM to condense them into a coherent budgeted storyboard."
            )
            condensed_panels = self._condense_panels_to_budget(final_panels, max_panels)
            if condensed_panels is not None:
                final_panels = condensed_panels
            else:
                print(
                    f"Falling back to representative panel selection "
                    f"(dropped {len(final_panels) - max_panels} extra panels)."
                )
                final_panels = self._select_representative_panels(final_panels, max_panels)

        return f"\n\n{panel_delimiter}\n\n".join(final_panels)

    def generate_storyboard(self, chunks: list[str], master_prompt: str, shots_per_page: int = 0,
                            bible_text: str = "", **kwargs):
        print("Executing 'Storyboard Generator' node...")

        if not chunks:
            raise ValueError("FATAL ERROR: 'chunks' input is empty.")

        if bible_text is None:
            bible_text = kwargs.get("character_bible_text", "")
        bible_text = (bible_text or "").strip()
        cached = llm_cache.load("storyboard", STORYBOARD_CACHE_VERSION, master_prompt, shots_per_page, bible_text, *chunks)
        if cached is not None:
            print("♻️ Storyboard loaded from disk cache (same script + prompt). Delete the llm_cache folder or set S2V_DISABLE_LLM_CACHE=1 to regenerate.")
            return (cached,)

        cast_sheet = ""
        if bible_text:
            cast_sheet = (
                "\n\nCAST SHEET (canonical characters):\n"
                f"{bible_text}\n"
                "NAMING RULES: In SUBJECT and ACTION_DESCRIPTION, always call these characters "
                "by the canonical name exactly as written above. NEVER use pronouns "
                "(he/she/they/it) or vague descriptors ('the boy', 'the hero') to refer to "
                "them - repeat the canonical name instead."
            )
            print(f"Storyboard: cast sheet with {len(bible_text.splitlines())} character line(s) injected into every chunk.")

        # Density-based budgets: each chunk gets panels proportional to its length,
        # so every part of the script is covered regardless of what earlier chunks did.
        chunk_budgets = None
        total_budget = 0
        if shots_per_page > 0:
            chunk_budgets = [
                max(
                    self._minimum_panel_budget_for_chunk(c),
                    int(shots_per_page * len(c) / PAGE_CHARS + 0.5),
                )
                for c in chunks
            ]
            total_budget = sum(chunk_budgets)
            print(f"Panel density: {shots_per_page} shots/page -> budgets per chunk {chunk_budgets} (total {total_budget}).")

        all_responses = []
        chunk_count = len(chunks)

        # Track the panel offset globally for this run
        total_panels_so_far = 0
        previous_tail = ""

        for i, chunk_content in enumerate(chunks):
            chunk_content = self._annotate_scene_boundaries(chunk_content)
            scene_boundary_instruction = (
                "\n\nSCENE CONTINUITY RULES:"
                "\n- Lines beginning with EXT., INT., INT./EXT., EXT./INT., or SCENE BOUNDARY are HARD CUTS."
                "\n- Start a new storyboard panel at every hard cut."
                "\n- Never blend locations across a hard cut. Do not put an interior character over the previous exterior background."
                "\n- After a hard cut, the new panel's ACTION_DESCRIPTION must describe only the new location unless the script explicitly says the previous location is visible."
                "\n\nVIDEO MODEL READABILITY RULES:"
                "\n- Treat each panel as one generated video section, not a paragraph of screenplay."
                "\n- Write concrete visible objects, body motion, facial expression, prop interaction, and camera movement."
                "\n- Avoid abstract words like realizes, understands, thinks, remembers, decides, feels, or knows unless they are shown through visible expression or action."
                "\n- Include KEYFRAME_DESCRIPTION, MOTION_DESCRIPTION, CAMERA_MOTION, and CONTINUITY_ANCHORS labels whenever the master prompt format allows them."
                "\n- Include SCENE_ID and TRANSITION on every panel. Reuse SCENE_ID only for the same place, time, and lighting."
                "\n- TRANSITION must be CONTINUE only for an uninterrupted action that should reuse the previous final frame. Use CUT for a new framing, location, time, subject, or independent story beat."
                "\n- Keep positive visual descriptions polished, fully colored, hand-painted 2D anime; require rich opaque color and softly painted surfaces, and do not include photo, live action, realistic, CGI, or 3D terms."
            )
            budget_instruction = ""
            if chunk_budgets is not None:
                pages = max(1, int(len(chunk_content) / PAGE_CHARS + 0.5))
                budget_instruction = (
                    f"\n\nPANEL BUDGET: This chunk is roughly {pages} page(s) of script. "
                    f"Create AT MOST {chunk_budgets[i]} final panels for it. This is a final "
                    "storyboard budget, not a draft budget. Do not create extra panels and assume "
                    "they will be trimmed later. Plan the whole chunk first, then output only the "
                    "best panels that represent the story. Choose the most important visual beats "
                    "across the whole chunk, not just the first beats. Preserve beginning, middle, "
                    "and ending coverage, and keep hard scene cuts represented. Merge minor moments "
                    "and consecutive dialogue lines into a single panel rather than creating one "
                    "panel per line."
                )

            msg = f"Storyboard: generating panels for chunk {i+1}/{chunk_count}..."
            print(msg, flush=True)
            announce_to_ui(msg)
            # 1. Inject the counter hint into the prompt
            offset_instruction = f"\n\nCONTINUITY RULE: You are currently processing from chunk {i+1} of {chunk_count}. " \
                                 f"Start your panel numbering at 'PANEL {total_panels_so_far + 1:03}'."

            prior_shot_context = ""
            if previous_tail:
                prior_shot_context = (
                    "\n\nPREVIOUS APPROVED STORYBOARD TAIL (context only; do not repeat these panels):\n"
                    f"{previous_tail}\n"
                    "The first new panel must advance beyond this tail. Preserve the same SCENE_ID only "
                    "if the script continues in the same location, time, and lighting; otherwise start a new "
                    "SCENE_ID and mark TRANSITION: CUT."
                )

            full_prompt = (
                f"{master_prompt}{cast_sheet}{scene_boundary_instruction}\n{offset_instruction}"
                f"{budget_instruction}{prior_shot_context}\n\n{chunk_content}"
            )
            
            response_text = ""
            max_retries = 3
            for attempt in range(max_retries):
                response_text = ask_gemini_via_relay(full_prompt)
                if not response_text.startswith("Error:"):
                    break
                import time
                time.sleep(2)

            if response_text.startswith("Error:"):
                raise RuntimeError(f" FATAL ERROR on chunk {i+1}: {response_text}")
            
            all_responses.append(response_text)
            response_panels = self._split_unique_panels(response_text)
            if response_panels:
                previous_tail = "\n\n--- PANEL BREAK ---\n\n".join(response_panels[-2:])[-5000:]
            
            new_panels = re.findall(r'PANEL\s+\d+', response_text, re.IGNORECASE)
            total_panels_so_far += len(new_panels)
        
        raw_storyboard_output = "\n".join(all_responses)
        final_storyboard = self._post_process_storyboard(raw_storyboard_output, total_budget)

        final_count = len(re.findall(r'PANEL\s+\d+', final_storyboard, re.IGNORECASE))
        print(f"Storyboard generation complete. Total panels: {final_count}")
        llm_cache.save("storyboard", final_storyboard, STORYBOARD_CACHE_VERSION, master_prompt, shots_per_page, bible_text, *chunks)
        return (final_storyboard,)
