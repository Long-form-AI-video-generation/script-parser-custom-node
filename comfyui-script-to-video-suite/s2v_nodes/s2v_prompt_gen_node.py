import re
# Import our relay function
from .gemini_relay_client import ask_gemini_via_relay

# --- Helper function from your script ---
def split_storyboard_into_scenes(storyboard_text: str) -> list[str]:
    scenes = re.split(r'(?=PANEL 001)', storyboard_text)
    cleaned_scenes = [s.strip() for s in scenes if s.strip() and "PANEL" in s]
    print(f"Storyboard split into {len(cleaned_scenes)} scenes.")
    return cleaned_scenes

# --- The ComfyUI Node Class ---
class PromptGenerator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "storyboard_text": ("STRING",), # Accepts the output from the storyboard node
                "prompt_template": ("STRING", {
                    "default": "You are a prompt engineer for an AI video generator. Convert the following storyboard scene into a series of detailed prompts...",
                    "multiline": True
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("final_prompts",)
    FUNCTION = "generate_prompts"
    CATEGORY = "Script To Video Suite"

    def generate_prompts(self, storyboard_text: str, prompt_template: str):
        print("Executing 'Prompt Generator' node...")
        
        scenes = split_storyboard_into_scenes(storyboard_text)
        if not scenes:
            print("Warning: No scenes found in the storyboard text.")
            return ("",)

        all_generated_prompts = []
        for i, scene in enumerate(scenes):
            print(f"Generating prompts for scene {i+1}/{len(scenes)} via relay...")
            full_prompt = f"{prompt_template}\n\n--- STORYBOARD SCENE ---\n\n{scene}"
            
            response_text = ask_gemini_via_relay(full_prompt)
            if response_text.startswith("Error:"):
                print(f"WARNING: Relay error on scene {i+1}: {response_text}")
                all_generated_prompts.append(f"--- ERROR PROCESSING SCENE {i+1} ---")
            else:
                all_generated_prompts.append(response_text)
        
        final_output = "\n\n--- SCENE BREAK ---\n\n".join(all_generated_prompts)
        print("Final prompt generation complete.")
        return (final_output,)