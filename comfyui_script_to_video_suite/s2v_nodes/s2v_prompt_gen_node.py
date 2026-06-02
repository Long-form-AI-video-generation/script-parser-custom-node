import re
import os
import json
import json.decoder
from .gemini_relay_client import ask_gemini_via_relay

def load_master_prompt_from_file() -> str:
    filename = "prompt_generation_meta_prompt.txt"
    file_path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(file_path): 
        return "### MISSION\nConvert the following markdown storyboard panels into a single JSON object."
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return f.read()
    except: return "### MISSION\nConvert storyboard to JSON."

class PromptGenerator:
    """
    Node #3: Prompt Generator (S2V)
    Takes Markdown-formatted storyboards (with **LABELS:**) and 
    converts them into polished JSON prompts via LLM.
    """
    @classmethod
    def IS_CHANGED(cls, **kwargs): return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "storyboard_text": ("STRING", {"multiline": True}),
                "master_prompt": ("STRING", {"default": load_master_prompt_from_file(), "multiline": True}),
                "batch_size": ("INT", {"default": 15, "min": 1, "max": 50, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("final_prompts",)
    FUNCTION = "generate_prompts_in_batches" 
    CATEGORY = "Script To Video Suite"

    def _extract_json_robustly(self, text):
        """
        Extracts JSON by finding the first '{' and letting the 
        standard json decoder find the matching closing brace.
        """
        # 1. Clean markdown markers
        cleaned = text.replace("```json", "").replace("```", "").strip()
        
        # 2. Find the start of the JSON
        start_idx = cleaned.find('{')
        if start_idx == -1:
            raise ValueError(f"No JSON found in response. Raw: {text[:100]}")
        
        # 3. Use the Python json decoder to find the end of the object
        # raw_decode reads until the matching closing brace is found
        try:
            decoder = json.JSONDecoder()
            obj, end_idx = decoder.raw_decode(cleaned[start_idx:])
            return obj
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON structure: {e}")

    def _split_storyboard_into_panels(self, text: str) -> list[str]:
        """
        Improved Splitter: Correctly identifies panels in the **SHOT_TYPE:** 
        markdown format shown in your photo.
        """
        # Split by the word PANEL followed by digits, but keep the content together
        # This handles both plain "PANEL 001" and bold "**PANEL 001**"
        segments = re.split(r'(?i)(?=\bPANEL\s+\d+)', text)
        
        # Filter out intro text and ensure each segment actually contains panel data
        actual_panels = [s.strip() for s in segments if "SHOT_TYPE" in s.upper()]
        
        print(f"🎬 PromptGen: Detected {len(actual_panels)} markdown panels in input.")
        return actual_panels

    def generate_prompts_in_batches(self, storyboard_text: str, master_prompt: str, batch_size: int):
        if not storyboard_text or not storyboard_text.strip():
            raise ValueError("❌ PromptGenerator: Input text is empty!")

        all_panels = self._split_storyboard_into_panels(storyboard_text)
        if not all_panels:
            raise ValueError("❌ PromptGenerator: Could not find any panels in the input text. Check the format!")

        merged_meta_summary = ""
        merged_panels_list = []
        previous_summary = ""
        
        total_batches = (len(all_panels) + batch_size - 1) // batch_size

        for i in range(0, len(all_panels), batch_size):
            batch_num = (i // batch_size) + 1
            batch_data = all_panels[i:i + batch_size]
            batch_text = "\n\n".join(batch_data)
            
            continuity = f"\n\nCONTEXT FROM PREVIOUS SCENE: {previous_summary}\n" if previous_summary else ""
            
            full_prompt = f"{master_prompt}{continuity}\n\n### STORYBOARD DATA TO CONVERT:\n{batch_text}\n\nRESULT JSON:"
            
            response_text = ask_gemini_via_relay(full_prompt)
            
            if response_text.startswith("Error:"):
                raise Exception(f"❌ RELAY FAILURE: {response_text}")

            data = self._extract_json_robustly(response_text)
            
            if data:
                # Merge summary
                current_sum = data.get("meta_summary", "")
                if current_sum:
                    previous_summary = current_sum
                    merged_meta_summary += (" " + current_sum if merged_meta_summary else current_sum)
                
                # Merge panels
                merged_panels_list.extend(data.get("panels", []))
                print(f"✅ Batch {batch_num}/{total_batches}: Processed {len(data.get('panels', []))} panels.")
            else:
                print(f"❌ Batch {batch_num} failed to return valid JSON.")
                # We show the start of the failure in terminal for debugging
                print(f"AI Response was: {response_text[:150]}...")

        if not merged_panels_list:
            raise ValueError("❌ Pipeline Failed: No panels were successfully converted to JSON.")

        return (json.dumps({"meta_summary": merged_meta_summary, "panels": merged_panels_list}, indent=2),)