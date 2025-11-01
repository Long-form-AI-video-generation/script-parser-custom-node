from .gemini_relay_client import ask_gemini_via_relay


class ScriptSummarizer:
    """
    A ComfyUI node that summarizes a full script before chunking.
    Useful for providing high-level context to downstream nodes
    such as storyboard generation and prompt engineering.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "script_text": ("STRING", {
                    "default": "Paste your entire script text here...",
                    "multiline": True,
                }),
                "summary_prompt": ("STRING", {
                    "default": (
                        "You are an expert film analyst.\n"
                        "Summarize the following movie script in **concise bullet points**.\n"
                        "Focus on key events, main characters, tone, and story flow."
                    ),
                    "multiline": True,
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("summary_text",)
    FUNCTION = "summarize_script"
    CATEGORY = "Script To Video Suite"

    def summarize_script(self, script_text: str, summary_prompt: str):
        """
        Uses the Gemini relay API to summarize the given script text.
        Returns a clean summary as a single string.
        """
        print("Running Script Summarizer Node...")

        # Combine the user prompt and the input script
        full_prompt = f"{summary_prompt}\n\n--- SCRIPT START ---\n\n{script_text}\n\n--- END ---"

        # Send request to the relay server
        response = ask_gemini_via_relay(full_prompt)

        # Handle possible network or relay errors gracefully
        if response.startswith("Error:"):
            print(f"Gemini Relay Error: {response}")
            return (f"[Error during summarization]\n{response}",)

        print("Script summary generated successfully.")
        return (response,)
