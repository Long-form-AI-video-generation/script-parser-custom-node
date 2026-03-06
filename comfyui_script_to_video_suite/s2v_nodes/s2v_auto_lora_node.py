import json
import folder_paths
import os
import re
import difflib
from .gemini_relay_client import ask_gemini_via_relay

class AutoLoraLoader_S2V:
    """
    Scene-Aware Auto LoRA Loader

    Features
    --------
    1. Detects characters using Gemini
    2. Detects scene type using Gemini
    3. Maps characters -> LoRA files automatically
    4. Applies scene-aware strength biasing
    5. Outputs LORA_STACK for external merger node
    """

    _cached_map = None

    # INPUT TYPES
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_prompt": ("STRING", {"multiline": True}),
                "lora_strength": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 10.0,
                    "step": 0.1
                }),
            }
        }

    RETURN_TYPES = ("LORA_STACK",)
    RETURN_NAMES = ("lora_stack",)
    FUNCTION = "process_auto_loras"
    CATEGORY = "Script To Video Suite"

    
    # SCENE BIAS RULES
    SCENE_STRENGTH_BIAS = {
        "battle": 1.3,
        "action": 1.2,
        "dialogue": 1.0,
        "close_up": 1.25,
        "dream": 0.8,
        "flashback": 0.9,
        "wide_scene": 0.95,
        "default": 1.0
    }


    # LORA MAP CREATION
    @staticmethod
    def create_map_from_lora_folder():
        """
        Scan LoRA directory and build smart name map.
        """

        print("AutoLoRA: scanning LoRA folder...")

        auto_map = {}
        available_loras = folder_paths.get_filename_list("loras")

        for relative_path in available_loras:

            filename = os.path.basename(relative_path)
            name_no_ext = os.path.splitext(filename)[0]

            patterns_to_remove = [
                r'\blora\b', r'\bloras\b',
                r'^lora_', r'^loras_',
                r'_lora\b', r'_loras\b',
                r'v\d+\b', r'_v\d+\b',
                r'version\d+\b',
                r'rev\d+\b',
                r'final\b',
                r'end\b'
            ]

            clean_name = name_no_ext

            for pattern in patterns_to_remove:
                clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)

            clean_name = re.sub(r'[_-]+', ' ', clean_name).strip().lower()

            if clean_name and len(clean_name) > 1:

                if clean_name not in auto_map:
                    auto_map[clean_name] = relative_path

                raw_key = name_no_ext.lower()

                if raw_key not in auto_map:
                    auto_map[raw_key] = relative_path

        return auto_map


    # SMART MAP BUILDER
    def build_smart_lora_map(self):

        if AutoLoraLoader_S2V._cached_map is not None:
            return AutoLoraLoader_S2V._cached_map

        AUTO_MAP = self.create_map_from_lora_folder()

        HARDCODED_MAP = {
            "isaac": "isaac_15.safetensors",
        }

        SMART_MAP = AUTO_MAP.copy()

        for char, filename in HARDCODED_MAP.items():
            SMART_MAP[char] = filename
            print(f"AutoLoRA: override '{char}' -> '{filename}'")

        AutoLoraLoader_S2V._cached_map = SMART_MAP

        print(
            f"AutoLoRA: SmartMap built with {len(SMART_MAP)} entries"
        )

        return SMART_MAP


    # GEMINI CHARACTER EXTRACTION
    def extract_characters(self, prompt):

        instruction = (
            "Extract ONLY proper character names from the text. "
            "Return JSON list. Example: [\"Isaac\", \"Neo\"]. "
            "Ignore generic words like man, woman, soldier."
        )

        query = f"{instruction}\n\nText:\n{prompt}"

        try:

            response = ask_gemini_via_relay(query)

            cleaned = response.replace("```json", "").replace("```", "").strip()

            result = json.loads(cleaned)

            if isinstance(result, list):
                return result

        except Exception as e:
            print(f"AutoLoRA: character extraction failed: {e}")

        return []

    # SCENE DETECTION
    def detect_scene_type(self, prompt):

        instruction = (
            "Classify the scene type from this text. "
            "Return ONLY one word from this list:\n"
            "battle, action, dialogue, close_up, dream, flashback, wide_scene\n"
            "If unsure return 'default'."
        )

        query = f"{instruction}\n\nText:\n{prompt}"

        try:

            response = ask_gemini_via_relay(query)

            scene = response.strip().lower()

            if scene in self.SCENE_STRENGTH_BIAS:
                return scene

        except Exception as e:
            print(f"AutoLoRA: scene detection failed: {e}")

        return "default"

    # MAIN PROCESS FUNCTION
    def process_auto_loras(self, image_prompt, lora_strength):

        LORA_MAP = self.build_smart_lora_map()

        print(f"AutoLoRA: analyzing prompt")

        characters = self.extract_characters(image_prompt)

        if not characters:
            print("AutoLoRA: no characters detected")
            return ([],)

        print(f"AutoLoRA: detected characters {characters}")

        scene_type = self.detect_scene_type(image_prompt)

        print(f"AutoLoRA: detected scene '{scene_type}'")

        bias = self.SCENE_STRENGTH_BIAS.get(scene_type, 1.0)

        final_strength = lora_strength * bias

        print(f"AutoLoRA: strength bias applied -> {final_strength}")

        available_loras = folder_paths.get_filename_list("loras")

        lora_stack = []

        for char in characters:

            clean = char.lower().strip()

            target_key = None

            if clean in LORA_MAP:
                target_key = clean

            else:

                matches = difflib.get_close_matches(
                    clean,
                    LORA_MAP.keys(),
                    n=1,
                    cutoff=0.6
                )

                if matches:
                    target_key = matches[0]

                    print(f"AutoLoRA: fuzzy match '{char}' -> '{target_key}'")

            if not target_key:
                print(f"AutoLoRA: no mapping for '{char}'")
                continue

            filename = LORA_MAP[target_key]

            if filename not in available_loras:
                print(f"AutoLoRA: missing file '{filename}'")
                continue

            print(f"AutoLoRA: loading LoRA '{filename}'")

            lora_stack.append(
                (filename, final_strength, final_strength)
            )

        return (lora_stack,)