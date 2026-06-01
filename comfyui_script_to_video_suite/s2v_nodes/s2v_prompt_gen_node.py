import re
import os
import json 
from .gemini_relay_client import ask_gemini_via_relay

# --- INTERNAL FALLBACK PROMPT ---
# This ensures the node is functional even if the .txt file is missing.
INTERNAL_FALLBACK_PROMPT = """### MISSION
You are a Data Transformation Engine. Your task is to convert the provided storyboard text into a single JSON object.

### REQUIRED FORMAT
{
  "meta_summary": "A brief summary of the overall scene context...",
  "panels": [
    {
      "panel_number": 1,
      "image_prompt": "masterpiece, best quality, anime style, cinematic still, [Character Name], [Action], [Environment]",
      "video_prompt": "Describe 1 short sentence of subtle motion."
    }
  ]
}

### RULES
1. You MUST include character names in the image_prompt.
2. Output ONLY valid JSON. No conversational text.
"""

def load_master_prompt_from_file() -> str:
    """Lazy loads the master prompt from the local directory."""
    filename = "prompt_generation_meta_prompt.txt"
    file_path = os.path.join(os.path.dirname(__file__), filename)
    
    if not os.path.exists(file_path):
        return INTERNAL_FALLBACK_PROMPT
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return INTERNAL_FALLBACK_PROMPT

class PromptGenerator:
    """
    A custom node that takes a full storyboard, breaks it into batches,
    calls an LLM to process each batch, and COMBINES the JSON results 
    into a single valid JSON output with context chaining.
    """
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "storyboard_text": ("STRING", {"multiline": True}),
                "master_prompt": ("STRING", {
                    "default": load_master_prompt_from_file(),
                    "multiline": True
                }),
                "batch_size": ("INT", {"default": 50, "min": 10, "max": 200, "step": 10}),
            },
            "optional": {
                "debug_mode": ("BOOLEAN", {"default": False}),
                "debug_filepath": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("final_prompts",)
    FUNCTION = "generate_prompts_in_batches"
    CATEGORY = "Script To Video Suite"

    def _extract_json(self, text):
        """Finds and extracts the JSON object from LLM responses that include chat text."""
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            return match.group(1)
        
        # If no brackets found, check if it's just raw summary text
        if "PANEL" in text or "Setting" in text:
            error_hint = "The AI returned a TEXT summary instead of JSON DATA. Check your master prompt."
            raise ValueError(f"❌ AI FORMAT ERROR:\n{error_hint}\n\nAI Said: {text[:150]}...")
        return text

    def _split_storyboard_into_panels(self, storyboard_text: str) -> list[str]:
        """Splits the full storyboard into individual panels using delimiters."""
        panels = re.split(r'\s*--- PANEL BREAK ---\s*|(?=PANEL\s+\d+)', storyboard_text)
        return [p.strip() for p in panels if p.strip() and p.startswith("PANEL")]

    def generate_prompts_in_batches(self, storyboard_text: str, master_prompt: str, batch_size: int, debug_mode: bool = False, debug_filepath: str = ""):
        
        # 1. Handle Debug Mode
        if debug_mode:
            print("💡 Debug Mode: Loading storyboard from file.")
            if not os.path.exists(debug_filepath):
                raise FileNotFoundError(f"Debug file not found: {debug_filepath}")
            with open(debug_filepath, 'r', encoding='utf-8') as f:
                storyboard_text = f.read()
        
        if not storyboard_text or not storyboard_text.strip():
            raise ValueError("❌ FATAL ERROR: Input 'storyboard_text' is empty!")

        # 2. Segment Panels
        all_panels = self._split_storyboard_into_panels(storyboard_text)
        if not all_panels:
            print("⚠️ Warning: No 'PANEL' keywords found. Returning empty.")
            return ("",)

        merged_meta_summary = ""
        merged_panels_list = []
        previous_batch_context = "" # For context chaining
        
        total_batches = (len(all_panels) + batch_size - 1) // batch_size

        # 3. Process Batches
        for i in range(0, len(all_panels), batch_size):
            batch_num = (i // batch_size) + 1
            print(f"\n--- Processing Batch {batch_num}/{total_batches} ---")
            
            batch_of_panels = all_panels[i:i + batch_size]
            batch_storyboard_text = "\n\n--- PANEL BREAK ---\n\n".join(batch_of_panels)
            
            # Inject context from the previous batch to maintain consistency
            context_injection = ""
            if previous_batch_context:
                context_injection = f"\n\n--- PREVIOUS CONTEXT ---\n{previous_batch_context}\n(Continue the story from here)\n"

            full_prompt = f"{master_prompt}{context_injection}\n\n--- STORYBOARD TO PROCESS ---\n\n{batch_storyboard_text}"
            
            # Call Relay
            response_text = ask_gemini_via_relay(full_prompt)
            
            if response_text.startswith("Error:"):
                raise Exception(f"❌ RELAY FAILURE on Batch {batch_num}: {response_text}")

            # 4. Extract and Parse JSON
            try:
                # Clean markdown blocks
                raw_text = response_text.replace("```json", "").replace("```", "").strip()
                json_str = self._extract_json(raw_text)
                batch_data = json.loads(json_str)
                
                # Update chaining context and merge summary
                batch_summary = batch_data.get("meta_summary", "")
                if batch_summary:
                    previous_batch_context = batch_summary
                    merged_meta_summary += (" " + batch_summary if merged_meta_summary else batch_summary)
                
                # Merge panels
                batch_panels = batch_data.get("panels", [])
                if isinstance(batch_panels, list):
                    merged_panels_list.extend(batch_panels)
                    print(f"✅ Batch {batch_num}: Merged {len(batch_panels)} panels.")
                else:
                    raise ValueError(f"Batch {batch_num}: 'panels' key is not a list.")

            except json.JSONDecodeError as e:
                raise Exception(f"❌ JSON ERROR on Batch {batch_num}: {e}\n\nAI Response: {response_text[:150]}...")

        # 5. Final Assembly
        final_output = {
            "meta_summary": merged_meta_summary,
            "panels": merged_panels_list
        }
        
        print(f"✅ Successfully processed all {len(merged_panels_list)} panels.")
        return (json.dumps(final_output, indent=2),)