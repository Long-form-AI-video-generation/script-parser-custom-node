import json
import hashlib

class PromptUnpacker:
    """
    Node #4a: Parses the JSON output from PromptGenerator into clean, 
    usable lists of prompts, ready for iteration.
    """
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return { 
            "required": { 
                "prompt_text": ("STRING", {"multiline": True, "forceInput": True}), 
            } 
        }

    RETURN_TYPES = ("PROMPTS_LIST", "PROMPTS_LIST", "STRING",)
    RETURN_NAMES = ("image_prompts", "video_prompts", "meta_summary",)
    FUNCTION = "unpack_prompts"
    CATEGORY = "Script To Video Suite/Execution"

    def unpack_prompts(self, prompt_text: str):
        print("Executing 'Prompt Unpacker' (JSON Mode)...")
        
        if not prompt_text or not prompt_text.strip():
            error_message = "❌ FATAL ERROR: Input 'prompt_text' is empty! The Prompt Generator node returned nothing."
            print(error_message)
            raise ValueError(error_message)

        cleaned_text = prompt_text.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(cleaned_text)
            
            meta_summary = data.get("meta_summary", "No summary provided.")
            panels = data.get("panels", [])
            
            if not isinstance(panels, list):
                error_message = f"❌ ERROR: 'panels' key is not a list. Got: {type(panels)}"
                print(error_message)
                raise ValueError(error_message)

            image_prompts = []
            video_prompts = []

            for i, p in enumerate(panels):
                i_p = p.get("image_prompt", "")
                v_p = p.get("video_prompt", "")

                if not isinstance(i_p, str) or not i_p.strip():
                    raise ValueError(f"Panel {i + 1} is missing a non-empty image_prompt.")
                if not isinstance(v_p, str) or not v_p.strip():
                    raise ValueError(f"Panel {i + 1} is missing a non-empty video_prompt.")

                image_prompts.append(i_p)
                video_prompts.append(v_p)

            print(f"✅ Unpacked {len(image_prompts)} image prompts and {len(video_prompts)} video prompts.")
            
            return (image_prompts, video_prompts, meta_summary)

        except json.JSONDecodeError as e:
            error_msg = f"❌ FATAL ERROR: The LLM output was not valid JSON.\nParse Error: {e}\n\nSnippet: {cleaned_text[:200]}..."
            print(error_msg)
            raise ValueError(error_msg)

        except Exception as e:
            error_msg = f"❌ UNEXPECTED ERROR during unpacking: {e}"
            print(error_msg)
            raise ValueError(error_msg)


class PromptLoopBuilder_S2V:
    """
    Stateless helper for single-run long video workflows.
    It exposes the first prompts for the seed section and the complete video
    prompt list for an internal loop that carries frame context forward.
    """

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_prompts": ("PROMPTS_LIST",),
                "video_prompts": ("PROMPTS_LIST",),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 100000, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "PROMPTS_LIST", "INT", "INT",)
    RETURN_NAMES = (
        "first_image_prompt",
        "first_video_prompt",
        "all_video_prompts",
        "first_index",
        "total_panels",
    )
    FUNCTION = "build_prompt_loop"
    CATEGORY = "Script To Video Suite/Execution"

    def build_prompt_loop(self, image_prompts: list, video_prompts: list, start_index: int):
        if not image_prompts or not video_prompts:
            raise ValueError("Prompt Loop Builder: image_prompts and video_prompts must not be empty.")

        if len(image_prompts) != len(video_prompts):
            raise ValueError(
                f"Prompt Loop Builder: prompt list length mismatch "
                f"({len(image_prompts)} image prompts vs {len(video_prompts)} video prompts)."
            )

        if start_index < 0 or start_index >= len(video_prompts):
            raise ValueError(
                f"Prompt Loop Builder: start_index {start_index} is outside "
                f"the prompt range 0..{len(video_prompts) - 1}."
            )

        first_image_prompt = image_prompts[start_index]
        first_video_prompt = video_prompts[start_index]

        if not isinstance(first_image_prompt, str) or not first_image_prompt.strip():
            raise ValueError(f"Prompt Loop Builder: image prompt at index {start_index} is empty.")
        if not isinstance(first_video_prompt, str) or not first_video_prompt.strip():
            raise ValueError(f"Prompt Loop Builder: video prompt at index {start_index} is empty.")

        print(
            f"✅ Prompt Loop Builder: Prepared {len(video_prompts)} prompts, "
            f"starting at index {start_index}."
        )
        return (first_image_prompt, first_video_prompt, video_prompts, start_index, len(video_prompts))


class SmartSequencer_S2V:
    """
    Node #4b (Production Grade): Automatically iterates through the prompt lists.
    - Unique counters per node instance (prevents cross-talk).
    - Auto-resets if the input prompt list changes (fingerprinting).
    - Manual reset toggle.
    - Returns individual prompts AND the full list for downstream processing.
    """
    
    # Store states globally for this class: { "node_id": {"index": 0, "last_hash": "..."} }
    _node_states = {}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_prompts": ("PROMPTS_LIST",),
                "video_prompts": ("PROMPTS_LIST",),
                "reset_counter": ("BOOLEAN", {"default": False, "label_on": "Reset NOW", "label_off": "Continue counting"}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID", 
            }
        }

    # Added "PROMPTS_LIST" to RETURN_TYPES to output the whole video prompt list
    RETURN_TYPES = ("STRING", "STRING", "PROMPTS_LIST", "INT", "INT",)
    RETURN_NAMES = ("image_prompt", "video_prompt", "all_video_prompts", "current_index", "total_panels",)
    FUNCTION = "execute_sequence"
    CATEGORY = "Script To Video Suite/Execution"

    def execute_sequence(self, image_prompts: list, video_prompts: list, reset_counter: bool, unique_id=None):
        total_panels = len(image_prompts)
        
        # 1. Validation (Fail-Loud)
        if total_panels == 0:
            error_message = "❌ Smart Sequencer: Input prompt list is empty."
            print(error_message)
            raise ValueError(error_message)
        
        if len(image_prompts) != len(video_prompts):
            error_message = f"❌ Smart Sequencer Mismatch: {len(image_prompts)} images vs {len(video_prompts)} videos."
            print(error_message)
            raise ValueError(error_message)

        # 2. Initialize or retrieve state for this specific node instance
        state_key = unique_id if unique_id is not None else "default"

        if state_key not in SmartSequencer_S2V._node_states:
            SmartSequencer_S2V._node_states[state_key] = {"index": 0, "last_hash": None}
        
        state = SmartSequencer_S2V._node_states[state_key]

        # 3. AUTO-RESET Logic
        current_data_fingerprint = json.dumps(
            {"image_prompts": image_prompts, "video_prompts": video_prompts},
            ensure_ascii=False,
            sort_keys=True,
        )
        current_hash = hashlib.md5(current_data_fingerprint.encode()).hexdigest()

        if state["last_hash"] is not None and state["last_hash"] != current_hash:
            print(f"🔄 Smart Sequencer [{state_key}]: New script detected. Auto-resetting index to 0.")
            state["index"] = 0
        
        state["last_hash"] = current_hash

        # 4. MANUAL RESET Logic
        if reset_counter:
            print(f"🔄 Smart Sequencer [{state_key}]: Manual Reset Triggered.")
            state["index"] = 0

        # 5. Get current index and wrap around
        idx = state["index"] % total_panels
        
        # Retrieve the individual prompts
        i_prompt = image_prompts[idx]
        v_prompt = video_prompts[idx]

        print(f"🎬 Smart Sequencer [{state_key}]: Processing Panel #{idx + 1} of {total_panels}")

        # 6. Update index for the NEXT run
        state["index"] += 1

        
        return (i_prompt, v_prompt, video_prompts, idx, total_panels)
