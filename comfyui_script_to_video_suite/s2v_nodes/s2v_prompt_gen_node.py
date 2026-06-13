import re
import os
import json
import json.decoder
from .gemini_relay_client import ask_gemini_via_relay

def load_master_prompt_from_file() -> str:
    filename = "prompt_generation_meta_prompt.txt"
    file_path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(file_path): 
        return "### MISSION\nConvert storyboard to JSON."
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return f.read()
    except: return "### MISSION\nConvert storyboard to JSON."

class PromptGenerator:
    """
    Node #3: Prompt Generator (S2V)
    High-robustness version designed to repair 'Hallucinated Single Quotes' 
    and mixed-delimiter JSON common in smaller LLM responses.
    """
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
                if isinstance(obj, dict) and ("panels" in obj or "meta_summary" in obj):
                    return obj
            except:
                continue
        return None

    def _split_storyboard_into_panels(self, text: str) -> list[str]:
        segments = re.split(r'(?i)(?=\bPANEL\s+\d+)', text)
        return [s.strip() for s in segments if "SHOT_TYPE" in s.upper()]

    def generate_prompts_in_batches(self, storyboard_text: str, master_prompt: str, batch_size: int):
        if not storyboard_text or not storyboard_text.strip():
            raise ValueError("❌ Input 'storyboard_text' is empty!")

        all_panels = self._split_storyboard_into_panels(storyboard_text)
        if not all_panels:
            raise ValueError("❌ No valid panels found in input.")

        merged_meta_summary = ""
        merged_panels_list = []
        previous_summary = ""
        total_batches = (len(all_panels) + batch_size - 1) // batch_size

        for i in range(0, len(all_panels), batch_size):
            batch_num = (i // batch_size) + 1
            batch_text = "\n\n".join(all_panels[i:i + batch_size])
            
            continuity = f"\n\nCONTEXT FROM PREVIOUS SCENE: {previous_summary}\n" if previous_summary else ""
            
            syntax_enforcement = "\n\nIMPORTANT: Use ONLY double-quotes (\") for JSON keys and values. " \
                                 "If you use a single quote (') for a value, the system will crash."
            
            full_prompt = f"{master_prompt}{continuity}{syntax_enforcement}\n\n### STORYBOARD DATA:\n{batch_text}\n\nRESULT JSON:"
            
            print(f"--- 🤖 Processing Batch {batch_num}/{total_batches} ---")
            response_text = ask_gemini_via_relay(full_prompt)
            
            if response_text.startswith("Error:"):
                raise Exception(f"❌ RELAY FAILURE: {response_text}")

            data = self._extract_json_robustly(response_text)
            
            if data:
                batch_sum = data.get("meta_summary", data.get("summary", ""))
                if batch_sum:
                    previous_summary = batch_sum
                    merged_meta_summary += (" " + batch_sum if merged_meta_summary else batch_sum)
                
                panels = data.get("panels", data.get("storyboard", []))
                if isinstance(panels, list):
                    merged_panels_list.extend(panels)
                    print(f"✅ Batch {batch_num} success.")
            else:
                print("\n" + "!"*40)
                print(f"❌ BATCH {batch_num} FINAL PARSE FAILURE.")
                print(f"REPAIRED STRING ATTEMPTED:\n{response_text[:500]}")
                print("!"*40 + "\n")
                raise Exception(f"❌ JSON ERROR: Model refused to use correct quotes. Check terminal.")

        return (json.dumps({"meta_summary": merged_meta_summary, "panels": merged_panels_list}, indent=2),)