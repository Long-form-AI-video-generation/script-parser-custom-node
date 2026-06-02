import json
import folder_paths

class StringSwitch_S2V:
    """
    Logic gate to switch between workflow output and manual entry.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "manual_input": ("STRING", {"multiline": True, "default": ""}),
                "use_manual": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "generated_input": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("selected_string",)
    FUNCTION = "switch_logic"
    CATEGORY = "Script To Video Suite/Logic"

    def switch_logic(self, manual_input, use_manual, generated_input=None):
        if use_manual:
            if not manual_input or not manual_input.strip():
                error_msg = "❌ FATAL ERROR: 'use_manual' is True, but 'manual_input' is empty."
                raise ValueError(error_msg)
            return (manual_input,)
        
        if generated_input is None:
            raise ValueError("❌ FATAL ERROR: Switch is in Workflow Mode, but nothing is connected!")
        return (generated_input,)

class ListSwitch_S2V:
    """
    Logic gate for lists (Chunks or Prompt Lists).
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "manual_text": ("STRING", {"multiline": True, "default": ""}),
                "use_manual": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "generated_list": ("*",), 
            }
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("selected_list",)
    FUNCTION = "switch_logic"
    CATEGORY = "Script To Video Suite/Logic"

    def switch_logic(self, manual_text, use_manual, generated_list=None):
        if use_manual:
            return ([manual_text],)
        if generated_list is None:
            return ([],)
        return (generated_list,)

class S2V_TextViewer:
    """
    Universal viewer. Uses '*' wildcard to accept Strings, Lists, or Dicts.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("*", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "show_text"
    CATEGORY = "Script To Video Suite/Logic"
    OUTPUT_NODE = True

    def show_text(self, text):
        if isinstance(text, list):
            display_text = "\n---\n".join([str(x) for x in text])
        else:
            display_text = str(text)
        return {"ui": {"text": [display_text]}, "result": (display_text,)}

class ListToString_S2V:
    """
    BRIDGE NODE: Converts a PROMPTS_LIST (from Unpacker/Sequencer) into a STRING.
    Allows connecting the full list to standard String nodes.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompts_list": ("PROMPTS_LIST",),
                "delimiter": ("STRING", {"default": "\\n"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("joined_string",)
    FUNCTION = "convert"
    CATEGORY = "Script To Video Suite/Logic"

    def convert(self, prompts_list, delimiter):
        actual_delimiter = delimiter.replace("\\n", "\n")
        return (actual_delimiter.join(prompts_list),)

class DebugLoraStack_S2V:
    @classmethod
    def INPUT_TYPES(cls):
        return { "required": { "lora_stack": ("LORA_STACK",), } }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "debug_stack"
    CATEGORY = "Script To Video Suite/Logic"
    OUTPUT_NODE = True

    def debug_stack(self, lora_stack):
        if not lora_stack:
            info = "ℹ️ LoRA Stack is EMPTY."
        else:
            info = "📋 LoRAs:\n" + "\n".join([f"{x[0]} (Str: {x[1]})" for x in lora_stack])
        return {"ui": {"text": [info]}, "result": (info,)}