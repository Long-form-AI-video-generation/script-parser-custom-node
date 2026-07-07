
import os
import re
from .gemini_relay_client import ask_gemini_via_relay
from . import llm_cache
from .s2v_progress_node import announce_to_ui

# This ensures the node functions even if the external .txt file is missing.
DEFAULT_STORYBOARD_PROMPT = (
    "You are an expert anime director and storyboard artist. Your task is to read the "
    "following anime script chunk and break it down into a sequence of visual storyboard panels.\n\n"
    "For each key moment or line of dialogue, create a new panel.\n"
    "You must infer camera shots if they are not explicitly mentioned.\n\n"
    "**Follow these rules for EACH panel you generate:**\n"
    "1. Start each panel with a unique panel number (e.g., 'PANEL 001', 'PANEL 002').\n"
    "2. Include SHOT_TYPE, SUBJECT, ACTION_DESCRIPTION, and DIALOGUE labels.\n"
    "3. Separate panels with the delimiter: '--- PANEL BREAK ---'\n"
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
        print(f"⚠️ S2V Warning: {filename} not found. Using internal fallback prompt.")
        return DEFAULT_STORYBOARD_PROMPT
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"⚠️ S2V Warning: Could not read {filename}. Reason: {e}. Using internal fallback.")
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
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("storyboard_text",)
    FUNCTION = "generate_storyboard"
    CATEGORY = "Script To Video Suite"

    def _post_process_storyboard(self, raw_text: str) -> str:
        """Helper function to clean up and de-duplicate storyboard panels."""
        panel_delimiter = "--- PANEL BREAK ---"
        all_panels_raw = raw_text.split(panel_delimiter)
        
        final_panels = []
        seen_panels = set()

        for panel_block in all_panels_raw:
            panel_block = panel_block.strip()
            if not panel_block: 
                continue

            if panel_block not in seen_panels:
                final_panels.append(panel_block)
                seen_panels.add(panel_block)
                
        print(f"✅ De-duplication complete. Kept {len(final_panels)} unique panels.")
        return f"\n\n{panel_delimiter}\n\n".join(final_panels)

    def generate_storyboard(self, chunks: list[str], master_prompt: str):
        print("Executing 'Storyboard Generator' node...")
        
        if not chunks:
            raise ValueError("FATAL ERROR: 'chunks' input is empty.")

        cached = llm_cache.load("storyboard", master_prompt, *chunks)
        if cached is not None:
            print("♻️ Storyboard loaded from disk cache (same script + prompt). Delete the llm_cache folder or set S2V_DISABLE_LLM_CACHE=1 to regenerate.")
            return (cached,)

        all_responses = []
        chunk_count = len(chunks)
        
        # Track the panel offset globally for this run
        total_panels_so_far = 0 

        for i, chunk_content in enumerate(chunks):
            msg = f"📖 Storyboard: generating panels for chunk {i+1}/{chunk_count}..."
            print(msg, flush=True)
            announce_to_ui(msg)
            # 1. Inject the counter hint into the prompt
            offset_instruction = f"\n\nCONTINUITY RULE: You are currently processing from chunk {i+1} of {chunk_count}. " \
                                 f"Start your panel numbering at 'PANEL {total_panels_so_far + 1:03}'."
            
            full_prompt = f"{master_prompt}\n{offset_instruction}\n\n{chunk_content}"
            
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
            
            new_panels = re.findall(r'PANEL\s+\d+', response_text, re.IGNORECASE)
            total_panels_so_far += len(new_panels)
        
        raw_storyboard_output = "\n".join(all_responses)
        final_storyboard = self._post_process_storyboard(raw_storyboard_output)
        
        print(f"✅ Storyboard generation complete. Total panels: {total_panels_so_far}")
        llm_cache.save("storyboard", final_storyboard, master_prompt, *chunks)
        return (final_storyboard,)
