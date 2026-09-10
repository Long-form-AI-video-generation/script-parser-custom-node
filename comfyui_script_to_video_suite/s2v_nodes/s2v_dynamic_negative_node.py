from .gemini_relay_client import ask_gemini_via_relay

class DynamicNegativePrompt_S2V:
    """
    Node: Dynamic Negative Prompt (S2V)
    Uses LLM to analyze the positive prompt and automatically generate
    scene-specific negative prompt keywords to avoid video artifacts, appending
    them to the base negative prompt.
    """
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    @classmethod
    def INPUT_TYPES(cls):
        default_base = (
            "bright tones, overexposed, static, blurred details, subtitles, style, works, "
            "paintings, images, static, overall gray, worst quality, low quality, "
            "JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, "
            "poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, "
            "still picture, messy background, three legs, many people in the background, walking backwards"
        )
        return {
            "required": {
                "positive_prompt": ("STRING", {"multiline": True, "forceInput": True}),
                "base_negative_prompt": ("STRING", {"default": default_base, "multiline": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("negative_prompt",)
    FUNCTION = "generate_negative"
    CATEGORY = "Script To Video Suite"

    def generate_negative(self, positive_prompt: str, base_negative_prompt: str):
        if not positive_prompt or not positive_prompt.strip():
            print("Dynamic Negative Prompt: positive_prompt is empty. Returning base negative prompt.")
            return (base_negative_prompt,)

        prompt = (
            f"You are an AI video generation expert for Wan2.1 video generation.\n"
            f"Analyze this scene prompt:\n\"{positive_prompt}\"\n\n"
            f"Generate 5 to 8 specific negative prompt terms (comma-separated) to prevent video artifacts "
            f"for this specific type of scene (e.g., motion glitches, anatomical errors, background clutter, lighting issues).\n"
            f"Output ONLY the comma-separated negative keywords, nothing else."
        )

        try:
            print(" Requesting scene-specific negative keywords from Gemini LLM...")
            llm_negatives = ask_gemini_via_relay(prompt)
            cleaned_negatives = llm_negatives.replace("\n", "").strip()

            if cleaned_negatives and not cleaned_negatives.startswith("Error:"):
                combined = f"{base_negative_prompt.strip(', ')}, {cleaned_negatives}"
                print(f" Dynamic LLM Negatives Added: {cleaned_negatives}")
                return (combined,)
            else:
                print(f" LLM Relay returned error/empty: '{cleaned_negatives}'. Falling back to base negative prompt.")
                return (base_negative_prompt,)
        except Exception as e:
            print(f" LLM Relay exception: {e}. Falling back to base negative prompt.")
            return (base_negative_prompt,)
