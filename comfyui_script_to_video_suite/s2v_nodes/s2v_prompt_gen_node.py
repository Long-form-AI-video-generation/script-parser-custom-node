import re
import os
import json
import json.decoder
from .gemini_relay_client import ask_gemini_via_relay
from . import llm_cache
from .s2v_progress_node import announce_to_ui
from .s2v_shot_plan_node import normalize_transition

PROMPT_CACHE_VERSION = "wan-video-prompts-v4-painted-color"

WAN_STYLE_ANCHOR = (
    "polished full-color hand-painted Japanese fantasy animation frame, classic Studio Ghibli-inspired storybook "
    "anime aesthetic, rich opaque color coverage, lush gouache and watercolor backgrounds, soft "
    "natural sunlight, atmospheric depth, expressive rounded character designs, delicate colored "
    "contours, soft cel shading with subtle tonal variation, tactile organic textures, cinematic "
    "composition, finished theatrical animation still, same anime character design"
)

WAN_VIDEO_ANCHOR = (
    "single continuous polished full-color hand-painted anime shot, same character design, "
    "rich color palette and outfit, no shot change"
)

REALISM_TERMS = (
    "photorealistic", "photorealism", "photo realistic", "hyperrealistic", "realistic", "realism",
    "live action", "live-action", "film still", "camera photo look", "camera photo", "photo look",
    "photographic look", "film look", "realistic look", "photograph",
    "photography", "DSLR", "real person", "real people", "real human", "human actor",
    "cosplay", "cinematic realism", "realistic face", "realistic skin", "skin pores",
    "natural skin texture", "documentary", "news footage", "3d render", "3D render",
    "3d", "3D", "CGI", "game cinematic", "semi-realistic", "uncanny valley",
)

ABSTRACT_ACTION_REPLACEMENTS = {
    r"\brealizes?\b": "reacts with a visible change in expression",
    r"\bunderstands?\b": "pauses with focused eyes",
    r"\bthinks?\b": "looks aside with a thoughtful expression",
    r"\bremembers?\b": "stares at the object with a tense expression",
    r"\bdecides?\b": "straightens posture and moves with purpose",
    r"\bfeels?\b": "shows the emotion through facial expression and posture",
    r"\bknows?\b": "holds a focused gaze",
}

MOTION_HINT_RE = re.compile(
    r"\b(move|moves|moving|walk|walks|run|runs|turn|turns|look|looks|raise|raises|"
    r"lower|lowers|type|types|press|presses|reach|reaches|gesture|gestures|blink|blinks|"
    r"breathe|breathes|pan|pans|tilt|tilts|push|pull|track|tracks|zoom|shake|shakes|"
    r"glow|glows|flicker|flickers|flow|flows|drift|drifts)\b",
    re.IGNORECASE,
)

def load_master_prompt_from_file() -> str:
    filename = "prompt_generation_meta_prompt.txt"
    file_path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(file_path): 
        return "### MISSION\nConvert storyboard to JSON."
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return f.read()
    except: return "### MISSION\nConvert storyboard to JSON."

class PromptGenerator:
   
    MAX_ATTEMPTS = 3

    SCHEMA_CORRECTION = (
        "\n\nCRITICAL CORRECTION: Your previous response used the WRONG schema. "
        "Do NOT return 'storyboard', 'shot_type', 'subject' or 'action_description' keys. "
        "Return EXACTLY this structure:\n"
        '{"meta_summary": "...", "panels": [{"panel_number": 1, '
        '"scene_id": "scene_001", "transition_type": "cut", '
        '"image_prompt": "polished full-color hand-painted Japanese fantasy animation frame, ...", '
        '"video_prompt": "single continuous polished full-color hand-painted anime shot, ..."}]}\n'
        "Every panel MUST contain a non-empty image_prompt and video_prompt."
    )

    @classmethod
    def IS_CHANGED(cls, **kwargs): return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "storyboard_text": ("STRING", {"multiline": True}),
                "master_prompt": ("STRING", {"default": load_master_prompt_from_file(), "multiline": True}),
                "batch_size": ("INT", {"default": 10, "min": 1, "max": 50, "step": 1}),
            },
            "optional": {
                "bible_text": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Connect the Character Extractor's bible_text. The cast sheet is "
                               "shown to the LLM for EVERY batch so canonical names and "
                               "appearance descriptors survive into every prompt.",
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("final_prompts",)
    FUNCTION = "generate_prompts_in_batches" 
    CATEGORY = "Script To Video Suite"

    def _extract_json_robustly(self, text):
       
        cleaned = text.replace("```json", "").replace("```", "").strip()
        cleaned = cleaned.replace("“", "\"").replace("”", "\"")

        
        cleaned = re.sub(r'(:\s*)\'', r'\1"', cleaned)
        
       
        cleaned = re.sub(r'\'\s*([,\]\}])', r'"\1', cleaned)

        start_indices = [m.start() for m in re.finditer(r'\{', cleaned)]
        decoder = json.JSONDecoder()
        
        for start_idx in reversed(start_indices):
            json_snippet = cleaned[start_idx:]
            try:
                obj, _ = decoder.raw_decode(json_snippet)
                if isinstance(obj, dict) and ("panels" in obj or "meta_summary" in obj or "storyboard" in obj):
                    return obj
            except:
                continue

        recovered_panels = []
        seen = set()
        for start_idx in start_indices:
            try:
                obj, _ = decoder.raw_decode(cleaned[start_idx:])
            except Exception:
                continue
            if not self._panel_has_prompts(obj):
                continue
            key = (
                obj.get("panel_number"),
                obj.get("image_prompt"),
                obj.get("video_prompt"),
            )
            if key in seen:
                continue
            seen.add(key)
            recovered_panels.append(obj)

        if recovered_panels:
            summary = ""
            summary_match = re.search(r'"meta_summary"\s*:\s*"((?:\\.|[^"\\])*)"', cleaned)
            if summary_match:
                try:
                    summary = json.loads(f'"{summary_match.group(1)}"')
                except Exception:
                    summary = summary_match.group(1)
            print(
                f"🛠️ Recovered {len(recovered_panels)} complete panel(s) "
                "from a truncated prompt JSON response."
            )
            return {"meta_summary": summary, "panels": recovered_panels}
        return None

    def _panel_has_prompts(self, panel):
        return (
            isinstance(panel, dict)
            and isinstance(panel.get("image_prompt"), str) and panel["image_prompt"].strip()
            and isinstance(panel.get("video_prompt"), str) and panel["video_prompt"].strip()
        )

    def _panels_are_valid(self, panels):
        """True only if every panel has the non-empty prompts the Unpacker needs."""
        if not isinstance(panels, list) or not panels:
            return False
        return all(self._panel_has_prompts(p) for p in panels)

    @staticmethod
    def _clean_prompt_for_wan(text):
        text = str(text or "").replace('"', "'")
        text = text.replace("“", "'").replace("”", "'")
        for pattern, replacement in ABSTRACT_ACTION_REPLACEMENTS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        for term in sorted(REALISM_TERMS, key=len, reverse=True):
            text = re.sub(rf"\b{re.escape(term)}\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bmasterpiece\b|\bbest quality\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bcinematic still\b", "anime keyframe", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:no|not|never)\s+(?:a\s+|an\s+)?(?=,|\.|$)", "", text, flags=re.IGNORECASE)
        text = ", ".join(
            part.strip()
            for part in text.split(",")
            if part.strip() and not re.fullmatch(r"(?i)(?:no|not|never|a|an|the|\s)+", part.strip())
        )
        text = re.sub(r"\s*[,;]\s*[,;]+", ", ", text)
        text = re.sub(r"\s+", " ", text).strip(" ,.;")
        return text

    @staticmethod
    def _trim_prompt(text, max_chars):
        text = str(text or "").strip()
        if len(text) <= max_chars:
            return text
        cut = text[:max_chars].rsplit(",", 1)[0].strip()
        if len(cut) < max_chars * 0.55:
            cut = text[:max_chars].rsplit(" ", 1)[0].strip()
        return cut.rstrip(" ,.;")

    def _normalize_image_prompt_for_wan(self, prompt):
        body = self._clean_prompt_for_wan(prompt)
        body = re.sub(
            rf"(?i)^\s*{re.escape(WAN_STYLE_ANCHOR)}\s*,?\s*",
            "",
            body,
        )
        body = re.sub(
            r"(?i)\bstrict\s+2d\s+japanese\s+tv\s+anime\s+keyframe\b|\bstrict\s+2d\s+anime\b|"
            r"\bjapanese\s+tv\s+anime\s+screenshot\b|\bhand-drawn\s+cel\s+animation\b|"
            r"\bclean\s+black\s+ink\s+lineart\b|\bflat\s+cel-?shaded\s+colors\b|"
            r"\bstylized\s+anime\s+faces\b|\bpainterly\s+anime\s+background\b|"
            r"\bpolished\s+full-color\s+hand-painted\s+japanese\s+fantasy\s+animation\s+frame\b|"
            r"\b(?:classic\s+studio\s+ghibli-inspired|warm\s+whimsical)\s+storybook\s+anime\s+aesthetic\b|"
            r"\brich\s+opaque\s+color\s+coverage\b|\bfinished\s+theatrical\s+animation\s+still\b|"
            r"\bsame\s+anime\s+character\s+design\b",
            "",
            body,
        )
        body = self._clean_prompt_for_wan(body)
        if body:
            prompt = f"{WAN_STYLE_ANCHOR}, single coherent keyframe, {body}"
        else:
            prompt = f"{WAN_STYLE_ANCHOR}, single coherent keyframe"
        return self._trim_prompt(prompt, 950)

    def _normalize_video_prompt_for_wan(self, prompt, image_prompt):
        body = self._clean_prompt_for_wan(prompt)
        body = re.sub(r"(?i)\b(cut to|hard cut to|transition to|switch to)\b", "camera holds as", body)
        body = re.sub(r"(?i)\bscene changes?\b", "camera continues", body)
        if not body:
            body = "the visible subject continues the action with subtle body motion and a gentle camera push-in"
        elif not MOTION_HINT_RE.search(body):
            body = f"{body}, with subtle body motion and a gentle camera push-in"

        video_prompt = f"{WAN_VIDEO_ANCHOR}, {body}"
        if "anime" not in video_prompt.lower():
            video_prompt = f"2D anime motion, {video_prompt}"
        return self._trim_prompt(video_prompt, 520)

    def _normalize_panels_for_wan(self, panels):
        normalized = []
        previous_scene = ""
        for idx, panel in enumerate(panels or []):
            if not isinstance(panel, dict):
                continue
            image_prompt = self._normalize_image_prompt_for_wan(panel.get("image_prompt", ""))
            video_prompt = self._normalize_video_prompt_for_wan(panel.get("video_prompt", ""), image_prompt)
            transition = normalize_transition(
                panel.get("transition_type", panel.get("transition")),
                default="cut",
            )
            scene_id = re.sub(
                r"[^A-Za-z0-9_.-]+",
                "_",
                str(panel.get("scene_id") or "").strip(),
            ).strip("_")
            if idx == 0:
                transition = "cut"
                scene_id = scene_id or "scene_001"
            elif transition == "continue":
                scene_id = scene_id or previous_scene
                if scene_id != previous_scene:
                    transition = "cut"
            else:
                scene_id = scene_id or f"scene_{idx + 1:03d}"

            normalized.append({
                "panel_number": idx + 1,
                "scene_id": scene_id,
                "transition_type": transition,
                "image_prompt": image_prompt,
                "video_prompt": video_prompt,
            })
            previous_scene = scene_id
        return normalized

    def _synthesize_panels_from_storyboard(self, raw_panels):
        
        synthesized = []
        for idx, p in enumerate(raw_panels):
            if not isinstance(p, dict):
                return None
            subject = str(p.get("subject") or "").strip()
            shot = str(p.get("shot_type") or "").strip()
            action = str(p.get("action_description") or "").strip()
            if not (subject or action):
                return None
            parts = [s for s in (subject, shot.lower(), action) if s]
            video_prompt = action or f"subtle motion, {subject}"
            if subject and subject.lower() not in video_prompt.lower():
                video_prompt = f"{subject}: {video_prompt}"
            synthesized.append({
                "panel_number": p.get("panel", p.get("panel_number", idx + 1)),
                "scene_id": str(p.get("scene_id") or f"scene_{idx + 1:03d}"),
                "transition_type": normalize_transition(
                    p.get("transition_type", p.get("transition")),
                    default="cut",
                ),
                "image_prompt": f"{WAN_STYLE_ANCHOR}, " + ", ".join(parts),
                "video_prompt": video_prompt,
            })
        return synthesized or None

    def _split_storyboard_into_panels(self, text: str) -> list[str]:
        segments = re.split(r'(?i)(?=\bPANEL\s+\d+)', text)
        valid_panel_pattern = re.compile(
            r"(?i)\b(SHOT[_\s-]*TYPE|SUBJECT|ACTION[_\s-]*DESCRIPTION)\b"
        )
        return [s.strip() for s in segments if valid_panel_pattern.search(s)]

    def generate_prompts_in_batches(self, storyboard_text: str, master_prompt: str, batch_size: int,
                                    bible_text: str = "", **kwargs):
        if not storyboard_text or not storyboard_text.strip():
            raise ValueError("❌ Input 'storyboard_text' is empty!")

        all_panels = self._split_storyboard_into_panels(storyboard_text)
        if not all_panels:
            raise ValueError("❌ No valid panels found in input.")

        if bible_text is None:
            bible_text = kwargs.get("character_bible_text", "")
        bible_text = (bible_text or "").strip()
        cached = llm_cache.load("prompts", PROMPT_CACHE_VERSION, master_prompt, storyboard_text, batch_size, bible_text)
        if cached is not None:
            print("♻️ Prompts loaded from disk cache (same storyboard + prompt). Delete the llm_cache folder or set S2V_DISABLE_LLM_CACHE=1 to regenerate.")
            return (cached,)

        cast_sheet = ""
        if bible_text:
            cast_sheet = (
                "\n\nCAST SHEET (canonical characters):\n"
                f"{bible_text}\n"
                "Always use these canonical names in image_prompt and video_prompt."
            )
            print(f"📇 Prompt Generator: cast sheet with {len(bible_text.splitlines())} character line(s) injected into every batch.")

        merged_meta_summary = ""
        merged_panels_list = []
        previous_summary = ""
        total_batches = (len(all_panels) + batch_size - 1) // batch_size

        for i in range(0, len(all_panels), batch_size):
            batch_num = (i // batch_size) + 1
            batch_text = "\n\n".join(all_panels[i:i + batch_size])

            continuity = f"\n\nCONTEXT FROM PREVIOUS SCENE: {previous_summary}\n" if previous_summary else ""

            syntax_enforcement = (
                "\n\nIMPORTANT OUTPUT RULES:"
                "\n- Return ONE JSON object with EXACTLY these top-level keys: \"meta_summary\" (string) and \"panels\" (array)."
                "\n- Each panel MUST be: {\"panel_number\": 1, \"scene_id\": \"scene_001\", \"transition_type\": \"cut\", \"image_prompt\": \"polished full-color hand-painted Japanese fantasy animation frame, ...\", \"video_prompt\": \"single continuous polished full-color hand-painted anime shot, ...\"}."
                "\n- transition_type MUST be exactly \"cut\" or \"continue\". Use \"continue\" only when this section must start from the previous final frame during uninterrupted action in the same scene; otherwise use \"cut\"."
                "\n- Preserve SCENE_ID from the storyboard. A changed location, time, or lighting requires a new scene_id and transition_type \"cut\"."
                "\n- Do NOT output 'storyboard', 'shot_type', 'subject' or 'action_description' keys; translate their content INTO the prompts."
                "\n- If a panel has LOCATION, CHARACTER_APPEARANCE, KEYFRAME_DESCRIPTION, ACTION_DESCRIPTION, CAMERA_MOTION, MOTION_DESCRIPTION, or CONTINUITY_ANCHORS, merge those exact usable details into the prompts."
                "\n- image_prompt is a drawable finished full-color anime frame: one location, visible subject, appearance, key pose, action, props, lighting, and composition. Require rich opaque colors, softly painted surfaces, and a polished theatrical-animation finish."
                "\n- video_prompt is motion only: one continuous shot, one subject action, speed/amplitude, one camera movement, and what visibly changes during this shot. Do not repeat the full environment description from image_prompt."
                "\n- Preserve named characters exactly in both image_prompt and video_prompt; include the name even when appearance descriptors are added."
                "\n- video_prompt MUST name every character in the panel by canonical name AND include 2-3 of their signature visual descriptors (hair, outfit, colors) from CHARACTER_APPEARANCE or the cast sheet."
                "\n- When a named character is the subject, state that the character is visibly on screen, with clear face/body presence."
                "\n- Use positive anime descriptors only. Do not put realistic, live action, photo, photograph, cosplay, CGI, or 3D terms in image_prompt or video_prompt."
                "\n- Replace abstract mental verbs with visible behavior. For example, do not write 'Isaac realizes'; write 'Isaac's eyes widen and Isaac freezes with one hand over the keyboard'."
                "\n- Preserve scene-location boundaries exactly. If one panel is an exterior establishing shot and the next panel is an interior room, the next image_prompt MUST describe only the interior room; do not include the exterior building, skyline, window view, or previous background unless that panel explicitly mentions it."
                "\n- Never create composite/overlay prompts from adjacent panels. A character must not float over or appear inside the previous location after a hard cut."
                "\n- Use ONLY double-quotes (\") for JSON keys and values. A single quote (') as a delimiter will crash the system."
            )

            print(f"---  Processing Batch {batch_num}/{total_batches} ---")
            announce_to_ui(f"Generating prompts: batch {batch_num}/{total_batches}")

            batch_panels = None
            batch_summary = ""
            fallback_source = None
            last_response = ""
            correction = ""

            for attempt in range(1, self.MAX_ATTEMPTS + 1):
                full_prompt = f"{master_prompt}{cast_sheet}{continuity}{syntax_enforcement}{correction}\n\n### STORYBOARD DATA:\n{batch_text}\n\nRESULT JSON:"
                response_text = ask_gemini_via_relay(full_prompt)

                if response_text.startswith("Error:"):
                    raise Exception(f" RELAY FAILURE: {response_text}")

                last_response = response_text
                data = self._extract_json_robustly(response_text)

                if data:
                    candidate = data.get("panels", data.get("storyboard", []))
                    if self._panels_are_valid(candidate):
                        batch_panels = candidate
                        batch_summary = data.get("meta_summary", data.get("summary", ""))
                        break
                    if isinstance(candidate, list):
                        valid_candidate = [p for p in candidate if self._panel_has_prompts(p)]
                        if valid_candidate:
                            print(
                                f"🛠️ Batch {batch_num}: salvaged {len(valid_candidate)}/"
                                f"{len(candidate)} complete panel(s) from a partial response."
                            )
                            batch_panels = valid_candidate
                            batch_summary = data.get("meta_summary", data.get("summary", ""))
                            break
                    if fallback_source is None and isinstance(candidate, list):
                        fallback_source = (candidate, data.get("meta_summary", data.get("summary", "")))
                    print(f"Batch {batch_num} attempt {attempt}: wrong schema (panels missing image_prompt/video_prompt). Retrying with correction...")
                else:
                    print(f"Batch {batch_num} attempt {attempt}: response was not parseable JSON. Retrying with correction...")

                correction = self.SCHEMA_CORRECTION

            if batch_panels is None and fallback_source:
                synthesized = self._synthesize_panels_from_storyboard(fallback_source[0])
                if synthesized:
                    print(f"🛠️ Batch {batch_num}: retries exhausted; built {len(synthesized)} prompts locally from the model's storyboard-schema response.")
                    batch_panels = synthesized
                    batch_summary = fallback_source[1]

            if batch_panels is None:
                print("\n" + "!"*40)
                print(f"BATCH {batch_num} FAILED after {self.MAX_ATTEMPTS} attempts.")
                print(f"LAST RAW RESPONSE:\n{last_response[:2000]}")
                print("!"*40 + "\n")
                raise Exception(f"SCHEMA ERROR on Batch {batch_num}: model never returned the required panels JSON. Check terminal for the raw response.")

            if batch_summary:
                previous_summary = batch_summary
                merged_meta_summary += (" " + batch_summary if merged_meta_summary else batch_summary)

            merged_panels_list.extend(batch_panels)
            print(f"Batch {batch_num} success ({len(batch_panels)} panels).")

        merged_panels_list = self._normalize_panels_for_wan(merged_panels_list)
        final_prompts = json.dumps({"meta_summary": merged_meta_summary, "panels": merged_panels_list}, indent=2)
        llm_cache.save("prompts", final_prompts, PROMPT_CACHE_VERSION, master_prompt, storyboard_text, batch_size, bible_text)
        return (final_prompts,)
