# Import our relay function
from .gemini_relay_client import ask_gemini_via_relay

# --- Helper function from your script ---
def post_process_storyboard(raw_text: str) -> str:
    panel_delimiter = "--- PANEL BREAK ---"
    all_panels_raw = raw_text.split(panel_delimiter)
    
    final_panels = []
    seen_action_descriptions = set()
    

    for panel_block in all_panels_raw:
        panel_block = panel_block.strip()
        if not panel_block: continue

        action_desc = ""
        for line in panel_block.split('\n'):
            if line.strip().upper().startswith("ACTION_DESCRIPTION:"):
                action_desc = line.strip()
                break
        
        if action_desc and action_desc not in seen_action_descriptions:
            final_panels.append(panel_block)
            seen_action_descriptions.add(action_desc)
        elif not action_desc:
            final_panels.append(panel_block)
            
    print(f"De-duplication complete. Kept {len(final_panels)} unique panels.")
    return f"\n\n{panel_delimiter}\n\n".join(final_panels)

# --- The ComfyUI Node Class ---
class StoryboardGenerator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "chunks": ("CHUNKS",), # This must match the output type of the first node
                "prompt_template": ("STRING", {
                    "default": "You are a storyboard artist. Create storyboard panels from the following script text...",
                    "multiline": True
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("storyboard_text",)
    FUNCTION = "generate_storyboard"
    CATEGORY = "Script To Video Suite"

    def generate_storyboard(self, chunks: list[str], prompt_template: str):
        print("Executing 'Storyboard Generator' node...")
        all_responses = []

        # Loop through each chunk and call our relay
        for i, chunk_content in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)} via relay...")
            full_prompt = f"{prompt_template}\n\n--- SCRIPT CHUNK ---\n\n{chunk_content}"
            
            response_text = ask_gemini_via_relay(full_prompt)
            if response_text.startswith("Error:"):
                print(f"WARNING: Relay error on chunk {i+1}: {response_text}")
                all_responses.append(f"--- ERROR PROCESSING CHUNK {i+1} ---")
            else:
                all_responses.append(response_text)
        
        # Combine and clean up the results
        raw_storyboard_output = "\n".join(all_responses)
        final_storyboard = post_process_storyboard(raw_storyboard_output)
        
        print("Storyboard generation complete.")
        return (final_storyboard,)