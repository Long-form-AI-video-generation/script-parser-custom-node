import json
import os
import folder_paths
from .gemini_relay_client import ask_gemini_via_relay



def load_prompt_from_file(filename: str) -> str:
    """
    Loads text content from a file located in the same directory as this script.
    
    Args:
        filename: The name of the text file to load.
        
    Returns:
        The content of the file as a string, or an error message if not found.
    """
    
    current_dir = os.path.dirname(__file__)
    file_path = os.path.join(current_dir, filename)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"ERROR: Prompt file not found at {file_path}. Please make sure '{filename}' is in the same directory as the node's Python script."
        )
    except Exception as e:        
        raise IOError(f"ERROR: Could not read prompt file. Reason: {e}") from e

SYSTEM_PROMPT = load_prompt_from_file("fighting_scene_classifier_prompt.txt")


class FightingSceneDetector_S2V:
    """
    Detects if a given text input describes a fighting scene. 
    Uses Gemini via a relay server to classify the scene.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("condition",)
    FUNCTION = "detect_fighting_scene"
    CATEGORY = "Script To Video Suite/FightDetection"

    def detect_fighting_scene(self, input: str):

        if not input or not input.strip():
            print("⚠️ Empty prompt → no fighting")
            return (False,)

        full_query = f"{SYSTEM_PROMPT}\n\n{input.strip()}"

        print(f"ANALYZING: {input[:50]}...")

        try:
            response = ask_gemini_via_relay(full_query)

            if response.startswith("Error:"):
                print(f"❌ Gemini error: {response}")
                return (False,)

            cleaned = response.replace("```json", "").replace("", "").strip()
            data = json.loads(cleaned)

            return (bool(data.get("is_fighting", False)),)

        except Exception as e:
            print(f"⚠️ Detection failed: {e}")
            return (False,)

        
class DragonBallLoRAConditional_S2V:
    """
    Conditionally prepares a LoRA configuration for WanVideoModelLoader.
    Returns a LIST of dictionaries compatible with WanVideoWrapper.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "condition": ("BOOLEAN", {"forceInput": True}),
                "lora_name": (folder_paths.get_filename_list("loras"),),
                "strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = ("WANVIDLORA",)             # Matches WanVideoWrapper's expected type
    RETURN_NAMES = ("lora",)
    FUNCTION = "prepare_conditional_lora"
    CATEGORY = "Script To Video Suite/FightDetection"

    def prepare_conditional_lora(self, condition: bool, lora_name: str, strength: float
                                 ):

        if not condition:
            print("❌ Condition False: No LoRA configuration provided.")
            # Return None or empty structure so downstream sees no LoRA
            return (None,)

        print(f"✅ Condition True: Preparing LoRA config for '{lora_name}' ")
              

        lora_path = folder_paths.get_full_path("loras", lora_name)
        if lora_path is None:
            print(f"⚠️ LoRA file '{lora_name}' not found. No config returned.")
            return (None,)

        lora_config = {
            "path": lora_path,
            "strength": strength, 
            "name": os.path.splitext(lora_name)[0],
            # This configuration is consumed by WanVideoSetLoRAs, which applies
            # prompt-specific patches to a cloned patcher without merging a model.
            "merge_loras": False,
            "low_mem_load": False,
            "blocks": {},               
            "layer_filter": ""          
        }
        
        loras_list = [lora_config]

        return (loras_list,)
