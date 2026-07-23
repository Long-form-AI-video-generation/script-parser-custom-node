import json
import folder_paths
import os
import re
import difflib
from . import llm_cache
from .llm_manager import query_llm


CHARACTER_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "s2v_character_lora_entities",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "characters": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["characters"],
        },
    },
}


def _parse_character_response(response_text):
    cleaned_json = response_text.replace("```json", "").replace("```", "").strip()
    data = json.loads(cleaned_json)
    if isinstance(data, list):
        character_names = data
    elif isinstance(data, dict):
        character_names = data.get("characters", [])
    else:
        character_names = []
    return [str(name).strip() for name in character_names if str(name).strip()]

class AutoLoraLoader_S2V:
    """
    The 'Brain' Node.
    1. Scans prompt text using Gemini to find Character Names.
    2. Scans your disk to map names (e.g. "Isaac") to files (e.g. "isaac_15.safetensors").
    3. Outputs a LORA_STACK list to be used by an external Merger node.
    """

    # Class-level variable for cross-instance caching
    _cached_map = None  

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_prompt": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "lora_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.1}),
            },
        }

    RETURN_TYPES = ("LORA_STACK",)
    RETURN_NAMES = ("lora_stack",)
    FUNCTION = "process_auto_loras"
    CATEGORY = "Script To Video Suite"

    @staticmethod
    def create_map_from_lora_folder():
        """
        Builds a map of 'clean_name' -> 'relative/path/filename.safetensors'.
        Uses ComfyUI's internal scanner to handle subfolders automatically.
        """
        print("AutoLoRA: Scanning LoRA folder for dynamic mapping...")
        auto_map = {}
        
        # Get list of all LoRAs (includes subfolders like 'characters/isaac.safetensors')
        available_loras = folder_paths.get_filename_list("loras")
        print(available_loras)
        for relative_path in available_loras:
            filename_only = os.path.basename(relative_path)
            name_no_ext = os.path.splitext(filename_only)[0]
            
            # Regex Cleaning (Remove 'lora', versions, underscores, noise)
            patterns_to_remove = [
                r'\blora\b', r'\bloras\b', r'^lora_', r'^loras_', r'_lora\b', r'_loras\b',
                r'v\d+\b', r'_v\d+\b', r'version\d+\b', r'_version\d+\b',
                r'rev\d+\b', r'_rev\d+\b', r'final\b', r'last\b', r'end\b',
                r'put_loras_here'
            ]
            
            clean_name = name_no_ext
            for pattern in patterns_to_remove:
                clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
            
            # Normalize to lowercase and remove underscores
            clean_name = re.sub(r'[_-]+', ' ', clean_name).strip().lower()

            if clean_name and len(clean_name) > 1:
                if clean_name not in auto_map:
                    auto_map[clean_name] = relative_path
                
                # Also index by the raw lowercase name just in case
                raw_key = name_no_ext.lower()
                if raw_key not in auto_map:
                    auto_map[raw_key] = relative_path

        return auto_map

    def build_smart_lora_map(self):
        """
        Builds the final map. Hardcoded entries take priority.
        Uses Class-level caching to ensure the disk is only scanned once.
        """
        # Access cache via the CLASS name, not 'self'
        if AutoLoraLoader_S2V._cached_map is not None:
            return AutoLoraLoader_S2V._cached_map

        # Scan folder
        AUTO_MAP = self.create_map_from_lora_folder()
        
        # Priority Hardcoded Overrides
        HARDCODED_MAP = {
            "isaac": "isaac_15.safetensors",
        }

        # Merge
        SMART_MAP = AUTO_MAP.copy()
        for char, filename in HARDCODED_MAP.items():
            SMART_MAP[char] = filename
            print(f"AutoLoRA: Enforcing hardcoded map '{char}' -> '{filename}'")

        # Save to Class-level cache
        AutoLoraLoader_S2V._cached_map = SMART_MAP
        print(f"✅ AutoLoRA: Global SmartMap ready with {len(AutoLoraLoader_S2V._cached_map)} entries.")
        
        return AutoLoraLoader_S2V._cached_map

    def process_auto_loras(self, image_prompt, lora_strength):
        # Retrieve the map (will use cache if already built)
        LORA_MAP = self.build_smart_lora_map()

        system_instruction = (
            "You are an entity extraction assistant. "
            "Identify the main character names in the text below. "
            "Return ONLY JSON in this shape: {\"characters\": [\"Isaac\", \"Neo\"]}. "
            "If no specific characters are found, return {\"characters\": []}. "
            "Ignore generic terms like 'man', 'woman', 'soldier', 'robot'. "
            "Only return Proper Nouns."
        )

        full_query = f"{system_instruction}\n\nText to analyze: {image_prompt}"
        print(f"🕵️ AutoLoRA: Analyzing prompt: {image_prompt[:50]}...")

        character_names = []
        try:
            cached = llm_cache.load("auto_lora_characters", image_prompt)
            if cached is not None:
                character_names = cached
                print("♻️ AutoLoRA: Character detection loaded from disk cache.")
            else:
                response_text = query_llm(
                    full_query,
                    response_format=CHARACTER_RESPONSE_FORMAT,
                    system_message=system_instruction,
                )

                if response_text.startswith("Error:"):
                    print(f"❌ AutoLoRA: LLM Error - {response_text}")
                    return ([],)

                character_names = _parse_character_response(response_text)
                llm_cache.save("auto_lora_characters", character_names, image_prompt)

        except Exception as e:
            print(f"⚠️ AutoLoRA: Extraction failed ({e}). Loading 0 LoRAs.")
            return ([],)

        if not isinstance(character_names, list):
            print(f"⚠️ AutoLoRA: LLM returned JSON but not a list: {character_names}")
            return ([],)

        if not character_names:
            print("ℹ️ AutoLoRA: No characters found in text.")
            return ([],)

        print(f"🤖 AutoLoRA: Found entities: {character_names}")

        # Verify files exist on disk before adding to stack
        available_loras = folder_paths.get_filename_list("loras")
        lora_stack = []

        for char_name in character_names:
            clean_name = char_name.lower().strip()
            target_key = None

            # exact match
            if clean_name in LORA_MAP:
                target_key = clean_name
            else:
                # 2. Try Fuzzy Match (Similarity threshold 0.6)
                matches = difflib.get_close_matches(clean_name, LORA_MAP.keys(), n=1, cutoff=0.6)
                if matches:
                    target_key = matches[0]
                    print(f"🔍 AutoLoRA: Fuzzy match '{char_name}' -> '{target_key}'")

            if target_key:
                target_filename = LORA_MAP[target_key]
                if target_filename in available_loras:
                    print(f"✅ AutoLoRA: Mapping '{char_name}' -> '{target_filename}'")
                    lora_stack.append((target_filename, lora_strength, lora_strength))
                else:
                    print(f"❌ AutoLoRA: Mapped '{char_name}' to '{target_filename}', but file is missing!")
            else:
                print(f"ℹ️ AutoLoRA: Character '{char_name}' not found in mapping.")

        return (lora_stack,)
