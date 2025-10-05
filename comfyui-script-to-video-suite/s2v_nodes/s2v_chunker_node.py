import os
import fitz  # PyMuPDF
from pathlib import Path

# --- Helper functions from your script (moved inside the class or kept separate) ---
def extract_text_from_pdf(pdf_path: str) -> str:
    if not os.path.exists(pdf_path):
        return f"ERROR: PDF file not found at '{pdf_path}'"
    try:
        doc = fitz.open(pdf_path)
        full_text = "".join(page.get_text() for page in doc)
        doc.close()
        return full_text
    except Exception as e:
        return f"ERROR: Could not read PDF. Reason: {e}"

def chunk_text(text: str, chunk_size: int, overlap_size: int) -> list[str]:
    if overlap_size >= chunk_size:
        # Prevent infinite loops
        overlap_size = chunk_size - 1
        print("Warning: Overlap size was >= chunk size. Adjusting to prevent errors.")

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap_size
    return chunks

# --- The ComfyUI Node Class ---
class PDFChunker:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pdf_path": ("STRING", {"default": "X:\\path\\to\\your\\script.pdf"}),
                "chunk_size": ("INT", {"default": 4000, "min": 100, "max": 16000, "step": 100}),
                "overlap_size": ("INT", {"default": 400, "min": 0, "max": 8000, "step": 50}),
            }
        }

    RETURN_TYPES = ("CHUNKS",) # We define a custom output type name
    FUNCTION = "process_pdf"
    CATEGORY = "Script To Video Suite"

    def process_pdf(self, pdf_path: str, chunk_size: int, overlap_size: int):
        print("Executing 'PDF Chunker' node...")
        
        # 1. Extract text
        raw_text = extract_text_from_pdf(pdf_path)
        if raw_text.startswith("ERROR"):
            # If there's an error, we should raise an exception to stop the workflow
            raise Exception(raw_text)

        # 2. Chunk the text
        script_chunks = chunk_text(raw_text, chunk_size, overlap_size)
        print(f"PDF processed into {len(script_chunks)} chunks.")
        
        # The node MUST return a tuple. The first element is our list of chunks.
        return (script_chunks,)