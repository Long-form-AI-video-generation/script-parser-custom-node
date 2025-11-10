import re
import os 
from .gemini_relay_client import ask_gemini_via_relay
from pathlib import Path
import sys 

RAG_DIR = Path(__file__).parent / "scene-consistent-rag-systems"
if RAG_DIR.exists():
    sys.path.insert(0, str(RAG_DIR))

try:
    from main import rag_enrich_panel
    RAG_AVAILABLE = True
    print("RAG system loaded: scene-consistent-rag-systems/main.py")
except Exception as e:
    RAG_AVAILABLE = False
    print(f"RAG not available (will skip enrichment): {e}")
  

def load_master_prompt_from_file(filename: str) -> str:
    current_dir = os.path.dirname(__file__)
    file_path = os.path.join(current_dir, filename)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"ERROR: Prompt file not found at {file_path}. Please make sure '{filename}' is in the same directory as the node's Python script."
    except Exception as e:
        return f"ERROR: Could not read prompt file. Reason: {e}"

PROMPT_GENERATION_META_PROMPT = load_master_prompt_from_file("prompt_generation_meta_prompt.txt")

class PromptGenerator:
    """
    A custom node that takes a full storyboard, breaks it into batches,
    calls an LLM to process each batch, and then combines the final results.
    Includes a debug mode to load storyboard data from a local file.
    """
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        """
        Defines the input widgets for the node.
        - Adds optional 'debug_mode' and 'debug_filepath' for isolated testing.
        """
        return {
            "required": {
                "storyboard_text": ("STRING", {"multiline": True}),
                "master_prompt": ("STRING", {
                    "default": PROMPT_GENERATION_META_PROMPT,
                    "multiline": True
                }),
                "batch_size": ("INT", {"default": 50, "min": 10, "max": 200, "step": 10}),
            },
           
            "optional": {
                "debug_mode": ("BOOLEAN", {"default": False}),
                "debug_filepath": ("STRING", {"default": "C:\\path\\to\\your\\debug_storyboard.txt"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("final_prompts",)
    FUNCTION = "generate_prompts_in_batches"
    CATEGORY = "Script To Video Suite"

    def _split_storyboard_into_panels(self, storyboard_text: str) -> list[str]:
        """Splits the full storyboard into a list of individual panel strings."""
        panels = re.split(r'\s*--- PANEL BREAK ---\s*|(?=PANEL\s+\d+)', storyboard_text)
        cleaned_panels = [p.strip() for p in panels if p.strip() and p.startswith("PANEL")]
        print(f"✅ Storyboard split into {len(cleaned_panels)} individual panels.")
        return cleaned_panels

    def generate_prompts_in_batches(self, storyboard_text: str, master_prompt: str, batch_size: int, debug_mode: bool = False, debug_filepath: str = ""):
        
        # --- NEW: DEBUG MODE LOGIC ---
        if debug_mode:
            print("💡 DEBUG MODE IS ON. Ignoring 'storyboard_text' input and loading from file.")
            try:
                if not os.path.exists(debug_filepath):
                    raise FileNotFoundError(f"Debug file not found at path: {debug_filepath}")
                
                with open(debug_filepath, 'r', encoding='utf-8') as f:
                    storyboard_text = f.read()
                print(f"✅ Successfully loaded debug data from: {debug_filepath}")
            except Exception as e:
                # Raise an exception to make the node turn red in ComfyUI and show the error.
                error_message = f"❌ DEBUG ERROR: Failed to load file. Reason: {e}"
                print(error_message)
                raise e  # Stop execution
        else:
            print("Executing 'Prompt Generator' node in normal mode...")
        
        if not storyboard_text or storyboard_text.strip() == "":
            print("⚠️ WARNING: Storyboard text is empty (either from input or debug file). Aborting.")
            return ("",)

        all_panels = self._split_storyboard_into_panels(storyboard_text)
        if not all_panels:
            print("⚠️ WARNING: No valid panels found in storyboard text. Aborting.")
            return ("",)

        final_responses = []
        total_batches = (len(all_panels) + batch_size - 1) // batch_size

        for i in range(0, len(all_panels), batch_size):
            batch_num = (i // batch_size) + 1
            print(f"\n--- Processing Batch {batch_num}/{total_batches} ---")

            batch_of_panels = all_panels[i:i + batch_size]
            enriched_panels = []

            for idx, panel in enumerate(batch_of_panels):
                panel_no = i + idx + 1
                print(f"   Panel {panel_no}/{len(all_panels)} → ", end="")

                if RAG_AVAILABLE:
                    try:
                        enriched = rag_enrich_panel(panel)
                        enriched_panels.append(enriched)
                        print("RAG enriched")
                    except Exception as e:
                        print(f"RAG failed → using raw panel ({e})")
                        enriched_panels.append(panel)
                else:
                    print("RAG not available → using raw panel")
                    enriched_panels.append(panel)

            batch_text = "\n\n--- PANEL BREAK ---\n\n".join(enriched_panels)
            full_prompt = f"{master_prompt}\n\n--- STORYBOARD TO PROCESS ---\n\n{batch_text}"

            response_text = ask_gemini_via_relay(full_prompt)
            if response_text.startswith("Error:"):
                raise Exception(f"Relay error: {response_text}")

            final_responses.append(response_text)
            print(f"Batch {batch_num} done.")

        return ("\n\n--- BATCH SEPARATOR ---\n\n".join(final_responses),)