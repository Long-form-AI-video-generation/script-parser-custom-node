import json
from .gemini_relay_client import ask_gemini_via_relay


class SceneRouter_S2V:
    """
    Scene-Aware Control Node

    Classifies a storyboard panel or prompt into a high-level scene type
    and outputs routing signals that downstream nodes can use to adapt:
    - LoRA selection
    - Prompt structure
    - Generation strategy

    Scene Types:
    - dialogue
    - action
    - fighting
    - cinematic
    - emotional
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "scene_text": ("STRING", {"multiline": True, "forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING", "BOOLEAN", "BOOLEAN", "BOOLEAN", "BOOLEAN")
    RETURN_NAMES = (
        "scene_type",
        "is_action",
        "is_fighting",
        "is_dialogue",
        "is_cinematic",
    )
    FUNCTION = "route_scene"
    CATEGORY = "Script To Video Suite/Control"

    def route_scene(self, scene_text: str):
        if not scene_text or not scene_text.strip():
            raise ValueError("SceneRouter: Input scene_text is empty.")

        system_prompt = (
            "You are a scene classification system for AI video generation.\n"
            "Classify the following scene into ONE of these categories:\n"
            "- dialogue\n"
            "- action\n"
            "- fighting\n"
            "- cinematic\n"
            "- emotional\n\n"
            "Return ONLY valid JSON in the following format:\n"
            "{ \"scene_type\": \"dialogue\" }\n"
        )

        query = f"{system_prompt}\n\nSCENE:\n{scene_text.strip()}"

        try:
            response = ask_gemini_via_relay(query)

            if response.startswith("Error:"):
                print(f"❌ SceneRouter: LLM error -> {response}")
                return ("unknown", False, False, False, False)

            cleaned = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)

            scene_type = data.get("scene_type", "unknown").lower()

        except Exception as e:
            print(f"⚠️ SceneRouter: Failed to classify scene ({e})")
            return ("unknown", False, False, False, False)

        is_action = scene_type in ("action", "fighting")
        is_fighting = scene_type == "fighting"
        is_dialogue = scene_type == "dialogue"
        is_cinematic = scene_type in ("cinematic", "emotional")

        print(
            f"SceneRouter: Detected scene_type='{scene_type}' | "
            f"action={is_action}, fighting={is_fighting}, "
            f"dialogue={is_dialogue}, cinematic={is_cinematic}"
        )

        return (
            scene_type,
            is_action,
            is_fighting,
            is_dialogue,
            is_cinematic,
        )
