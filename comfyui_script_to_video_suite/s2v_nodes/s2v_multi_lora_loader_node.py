"""
Multi-LoRA loader node for the Script-To-Video suite.
Resolves LoRA names to filesystem paths.
Builds configuration dictionaries for each resolved LoRA.
Returns a list of LoRA configs or (None,) when none found.
"""

import folder_paths
import os

class MultiLoraLoader_S2V:
    """
    Prepares LoRA configuration dictionaries for downstream use.
    Resolves provided LoRA names to paths and validates files.
    Sets default merge and load metadata for each LoRA.
    Returns a list used by later loader/merger nodes.
    """

    @classmethod
    def INPUT_TYPES(cls):
        """
        Return the node's input type specification (required inputs).
        Declares `lora_stack` as the required `LORA_STACK` input.
        Expects tuples (name, strength_model, strength_clip).
        Only name and strength_model are used by this loader.
        """
        return {
            "required": {
                "lora_stack": ("LORA_STACK",), 
            }
        }

    RETURN_TYPES = ("WANVIDLORA",)
    RETURN_NAMES = ("loras_list",)
    FUNCTION = "prepare_loras"
    CATEGORY = "Script To Video Suite"

    def prepare_loras(self, lora_stack):
        if not lora_stack:
            print("⚠️ Empty lora_stack: No LoRA configurations provided.")
            return (None,)

        print(f"🔥 MultiLora: Processing stack with {len(lora_stack)} items...")

        loras_list = []

        for lora_name, strength_model, _ in lora_stack:
            #  Resolve LoRA file path
            resolved_path = folder_paths.get_full_path("loras", lora_name)
            
            # Fallback: check if lora_name is already an absolute path
            if resolved_path is None and os.path.exists(lora_name):
                resolved_path = os.path.realpath(lora_name)

            if resolved_path is None:
                print(f"❌ LoRA file not found: {lora_name}")
                continue

            # Build configuration dictionary 
            lora_config = {
                "path": resolved_path,
                "strength": strength_model,  
                "name": os.path.splitext(os.path.basename(lora_name))[0],
                "merge_loras": True,
                "low_mem_load": False,
                "blocks": {},
                "layer_filter": ""
            }
            
            loras_list.append(lora_config)
            print(f"   ✅ Added: {lora_name} (Strength: {strength_model})")

        if not loras_list:
            print("⚠️ No valid LoRAs found in stack.")
            return (None,)

        print(f"✅ Prepared {len(loras_list)} LoRA configuration(s)")
        return (loras_list,)


class MergeWanVideoLoras_S2V:
    """
    Combines optional WanVideoWrapper LoRA config lists.
    Useful when one branch selects character LoRAs and another branch selects
    a scene/action LoRA for the same prompt.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "lora_a": ("WANVIDLORA", {"forceInput": True}),
                "lora_b": ("WANVIDLORA", {"forceInput": True}),
                "lora_c": ("WANVIDLORA", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("WANVIDLORA",)
    RETURN_NAMES = ("loras",)
    FUNCTION = "merge_loras"
    CATEGORY = "Script To Video Suite"

    @staticmethod
    def _extend_loras(merged, lora_value):
        if not lora_value:
            return
        if isinstance(lora_value, list):
            merged.extend(item for item in lora_value if item)
            return
        if isinstance(lora_value, dict):
            merged.append(lora_value)
            return
        print(f"⚠️ MergeWanVideoLoras: Ignoring unsupported LoRA value: {type(lora_value).__name__}")

    def merge_loras(self, lora_a=None, lora_b=None, lora_c=None):
        merged = []
        self._extend_loras(merged, lora_a)
        self._extend_loras(merged, lora_b)
        self._extend_loras(merged, lora_c)

        if not merged:
            print("ℹ️ MergeWanVideoLoras: No LoRAs selected.")
            return (None,)

        print(f"✅ MergeWanVideoLoras: Merged {len(merged)} LoRA config(s).")
        return (merged,)
