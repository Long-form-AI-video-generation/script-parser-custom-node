import os
import fitz  # PyMuPDF

from .gemini_relay_client import ask_gemini_via_relay

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts all text content from a given PDF file."""
    if not os.path.exists(pdf_path):
        return f"ERROR: PDF file not found at '{pdf_path}'"
    try:
        doc = fitz.open(pdf_path)
        full_text = "".join(page.get_text() for page in doc)
        doc.close()
        return full_text
    except Exception as e:
        return f"ERROR: Could not read PDF. Reason: {e}"

# This is the main class for your custom node
class PDFToParsedScript:
    """
    A custom node that takes a PDF file path, extracts text, and uses an LLM
    to parse it into a structured script format.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pdf_path": ("STRING", {"default": "X:\\path\\to\\your\\script.pdf", "multiline": False}),
                "parsing_prompt": ("STRING", {
                    "default": "You are an expert script parser. Your task is to take the following raw script text and break it down into a structured list of scenes. Identify the scene heading, action lines, dialogue, and camera directions for each scene. Use '---SCENE BREAK---' to separate each scene.",
                    "multiline": True
                }),
                # Note: The model_name is now ignored, as the relay server controls the model.
                # We leave it in the UI to avoid breaking workflows, but it has no effect.
                "model_name": ("STRING", {"default": "gemini-pro (via relay)"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("parsed_script",)
    FUNCTION = "run_parsing"
    CATEGORY = "Script To Video Suite"

    def run_parsing(self, pdf_path: str, parsing_prompt: str, model_name: str):
        print("Executing 'PDF to Parsed Script' node...")
        
        # Step 1: Extract text from the PDF (unchanged)
        raw_text = extract_text_from_pdf(pdf_path)
        if raw_text.startswith("ERROR"):
            print(raw_text)
            return (raw_text,)

        # Step 2: Call our relay function instead of the Gemini API directly
        # --- MODIFIED BLOCK ---
        print(f"Sending script to relay server for parsing...")
        full_prompt = f"{parsing_prompt}\n\n--- SCRIPT CONTENT ---\n\n{raw_text}"
        
        # Call the function from our other file
        parsed_script = ask_gemini_via_relay(full_prompt)
        
        # Check if the relay function returned an error message
        if parsed_script.startswith("Error:"):
            print(parsed_script) # Print the specific error from the relay
            return (parsed_script,) # Return the error to the ComfyUI output
            
        print("Successfully received parsed script via relay.")
        # --- END OF MODIFIED BLOCK ---
        
        # Node outputs must always be returned as a tuple
        return (parsed_script,)