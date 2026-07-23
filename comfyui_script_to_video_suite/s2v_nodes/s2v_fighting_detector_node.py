import json
import os
import folder_paths
from . import llm_cache
from .llm_manager import query_llm



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


FIGHT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "s2v_fighting_scene_detection",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "is_fighting": {"type": "boolean"}
            },
            "required": ["is_fighting"],
        },
    },
}


def _parse_fighting_response(response_text: str) -> bool:
    cleaned = response_text.replace("```json", "").replace("```", "").strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")
    return bool(data.get("is_fighting", False))


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
            cached = llm_cache.load("fight_scene", input)
            if cached is not None:
                print("♻️ Fighting Scene Detector: result loaded from disk cache.")
                return (bool(cached),)

            response = query_llm(
                full_query,
                response_format=FIGHT_RESPONSE_FORMAT,
                system_message=SYSTEM_PROMPT,
            )

            if response.startswith("Error:"):
                print(f"❌ LLM error: {response}")
                return (False,)

            is_fighting = _parse_fighting_response(response)
            llm_cache.save("fight_scene", is_fighting, input)
            return (is_fighting,)

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
            "merge_loras": True,         
            "low_mem_load": False,
            "blocks": {},               
            "layer_filter": ""          
        }
        
        loras_list = [lora_config]

        return (loras_list,)
