import re
import os
import json
import json.decoder
from .gemini_relay_client import ask_gemini_via_relay
from . import llm_cache
from .s2v_progress_node import announce_to_ui

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
        '"image_prompt": "masterpiece, best quality, anime style, ...", '
        '"video_prompt": "..."}]}\n'
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
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("final_prompts",)
    FUNCTION = "generate_prompts_in_batches" 
    CATEGORY = "Script To Video Suite"

    def _extract_json_robustly(self, text):
        """
        The 'Repairman' logic:
        1. Finds all { } blocks.
        2. Specifically repairs the '"key": 'value'' pattern seen in logs.
        3. Decodes using raw_decode.
        """
        # 1. Clean markdown and common noise
        cleaned = text.replace("```json", "").replace("```", "").strip()
        cleaned = cleaned.replace("“", "\"").replace("”", "\"")

        # 2. REPAIR DELIMITERS: The AI is using ' instead of " for values.
        # This regex looks for: : followed by optional space and a single quote
        # It replaces it with : "
        cleaned = re.sub(r'(:\s*)\'', r'\1"', cleaned)
        
        # This regex looks for: a single quote followed by a comma, bracket, or brace
        # It replaces it with " and the separator
        cleaned = re.sub(r'\'\s*([,\]\}])', r'"\1', cleaned)

        # 3. Find every '{' and try to decode from there
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
        return None

    def _panels_are_valid(self, panels):
        """True only if every panel has the non-empty prompts the Unpacker needs."""
        if not isinstance(panels, list) or not panels:
            return False
        return all(
            isinstance(p, dict)
            and isinstance(p.get("image_prompt"), str) and p["image_prompt"].strip()
            and isinstance(p.get("video_prompt"), str) and p["video_prompt"].strip()
            for p in panels
        )

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
            synthesized.append({
                "panel_number": p.get("panel", p.get("panel_number", idx + 1)),
                "image_prompt": "masterpiece, best quality, anime style, " + ", ".join(parts),
                "video_prompt": action or f"subtle motion, {subject}",
            })
        return synthesized or None

    def _split_storyboard_into_panels(self, text: str) -> list[str]:
        segments = re.split(r'(?i)(?=\bPANEL\s+\d+)', text)
        valid_panel_pattern = re.compile(
            r"(?i)\b(SHOT[_\s-]*TYPE|SUBJECT|ACTION[_\s-]*DESCRIPTION)\b"
        )
        return [s.strip() for s in segments if valid_panel_pattern.search(s)]

    def generate_prompts_in_batches(self, storyboard_text: str, master_prompt: str, batch_size: int):
        if not storyboard_text or not storyboard_text.strip():
            raise ValueError("❌ Input 'storyboard_text' is empty!")

        all_panels = self._split_storyboard_into_panels(storyboard_text)
        if not all_panels:
            raise ValueError("❌ No valid panels found in input.")

        cached = llm_cache.load("prompts", master_prompt, storyboard_text, batch_size)
        if cached is not None:
            print("♻️ Prompts loaded from disk cache (same storyboard + prompt). Delete the llm_cache folder or set S2V_DISABLE_LLM_CACHE=1 to regenerate.")
            return (cached,)

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
                "\n- Each panel MUST be: {\"panel_number\": 1, \"image_prompt\": \"masterpiece, best quality, anime style, ...\", \"video_prompt\": \"...\"}."
                "\n- Do NOT output 'storyboard', 'shot_type', 'subject' or 'action_description' keys; translate their content INTO the prompts."
                "\n- Use ONLY double-quotes (\") for JSON keys and values. A single quote (') as a delimiter will crash the system."
            )

            print(f"--- 🤖 Processing Batch {batch_num}/{total_batches} ---")
            announce_to_ui(f"🧠 Generating prompts: batch {batch_num}/{total_batches}")

            batch_panels = None
            batch_summary = ""
            fallback_source = None
            last_response = ""
            correction = ""

            for attempt in range(1, self.MAX_ATTEMPTS + 1):
                full_prompt = f"{master_prompt}{continuity}{syntax_enforcement}{correction}\n\n### STORYBOARD DATA:\n{batch_text}\n\nRESULT JSON:"
                response_text = ask_gemini_via_relay(full_prompt)

                if response_text.startswith("Error:"):
                    raise Exception(f"❌ RELAY FAILURE: {response_text}")

                last_response = response_text
                data = self._extract_json_robustly(response_text)

                if data:
                    candidate = data.get("panels", data.get("storyboard", []))
                    if self._panels_are_valid(candidate):
                        batch_panels = candidate
                        batch_summary = data.get("meta_summary", data.get("summary", ""))
                        break
                    if fallback_source is None and isinstance(candidate, list):
                        fallback_source = (candidate, data.get("meta_summary", data.get("summary", "")))
                    print(f"⚠️ Batch {batch_num} attempt {attempt}: wrong schema (panels missing image_prompt/video_prompt). Retrying with correction...")
                else:
                    print(f"⚠️ Batch {batch_num} attempt {attempt}: response was not parseable JSON. Retrying with correction...")

                correction = self.SCHEMA_CORRECTION

            if batch_panels is None and fallback_source:
                synthesized = self._synthesize_panels_from_storyboard(fallback_source[0])
                if synthesized:
                    print(f"🛠️ Batch {batch_num}: retries exhausted; built {len(synthesized)} prompts locally from the model's storyboard-schema response.")
                    batch_panels = synthesized
                    batch_summary = fallback_source[1]

            if batch_panels is None:
                print("\n" + "!"*40)
                print(f"❌ BATCH {batch_num} FAILED after {self.MAX_ATTEMPTS} attempts.")
                print(f"LAST RAW RESPONSE:\n{last_response[:2000]}")
                print("!"*40 + "\n")
                raise Exception(f"❌ SCHEMA ERROR on Batch {batch_num}: model never returned the required panels JSON. Check terminal for the raw response.")

            if batch_summary:
                previous_summary = batch_summary
                merged_meta_summary += (" " + batch_summary if merged_meta_summary else batch_summary)

            merged_panels_list.extend(batch_panels)
            print(f"✅ Batch {batch_num} success ({len(batch_panels)} panels).")

        final_prompts = json.dumps({"meta_summary": merged_meta_summary, "panels": merged_panels_list}, indent=2)
        llm_cache.save("prompts", final_prompts, master_prompt, storyboard_text, batch_size)
        return (final_prompts,)
