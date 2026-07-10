"""
This node, "PDF Chunker (S2V)", is the starting point of the Script-to-Video pipeline.
It takes the path to a PDF file, extracts all its text content, and then splits that
text into smaller, manageable chunks. This is crucial for processing large scripts
that would otherwise exceed the context limits of language models. each chunk will be processed separately by the llm
"""




import os
import hashlib
import fitz  # PyMuPDF
from docling.document_converter import DocumentConverter

try:
    import folder_paths
except ImportError:
    folder_paths = None

class PDFChunker:
    """
    A custom node that extracts text from a PDF and splits it into overlapping chunks.
    This allows for processing of arbitrarily long scripts.
    """
    
    # Add documentation that will be visible in some ComfyUI frontends
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # A simple mechanism to suggest reloading when the code changes.
        return float("NaN")
 
    @classmethod
    def INPUT_TYPES(cls):
        """
        Defines the input widgets for the node.
        - pdf_path: The absolute path to the PDF script file.
        - chunk_size: The target character length for each chunk.
        - overlap_size: The number of characters from the end of one chunk to include at the beginning of the next, to maintain context.
        """
        return {
            "required": {
                "pdf_path": ("STRING", {"default": "/path/to/your/script.pdf"}),
                "chunk_size": ("INT", {"default": 4000, "min": 500, "max": 16000, "step": 100}),
                "overlap_size": ("INT", {"default": 400, "min": 0, "max": 8000, "step": 50}),
            }
        }

    RETURN_TYPES = ("CHUNKS", "STRING", "INT")
    RETURN_NAMES = ("chunks", "debug_text_output", "chunk_count")
    FUNCTION = "process_pdf"
    CATEGORY = "Script To Video Suite"

    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Uses Docling to extract structured Markdown text."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at '{pdf_path}'")
        
        try:
            
            converter = DocumentConverter()
            
            
            result = converter.convert(pdf_path)
            
            
            markdown_output = result.document.export_to_markdown()
            
            return markdown_output
            
        except Exception as e:
            raise IOError(f"Docling failed to process PDF. Reason: {e}")

    def _chunk_text(self, text: str, chunk_size: int, overlap_size: int) -> list[str]:
        """Helper function to split text into smaller, overlapping chunks."""
        if overlap_size >= chunk_size:
            overlap_size = chunk_size - 1
            print(f"Warning: Overlap size was >= chunk size. Adjusting to {overlap_size} to prevent errors.")

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap_size
        return chunks #lists of chunks 

    def _process_pdf_path(self, pdf_path: str, chunk_size: int, overlap_size: int, node_name: str):
        print(f"Executing '{node_name}' node...")

        raw_text = self._extract_text_from_pdf(pdf_path)
        script_chunks = self._chunk_text(raw_text, chunk_size, overlap_size)
        chunk_count = len(script_chunks)

        print(f"✅ PDF processed into {chunk_count} chunks.")

        # Create the debug string for visual inspection in other nodes
        debug_text = f"Total Chunks: {chunk_count}\n\n"
        debug_text += "\n\n--- CHUNK BREAK ---\n\n".join(script_chunks)

        # Return the list of chunks, the debug text, and the count
        return (script_chunks, debug_text, chunk_count)

    def process_pdf(self, pdf_path: str, chunk_size: int, overlap_size: int):
        return self._process_pdf_path(pdf_path, chunk_size, overlap_size, "PDF Chunker")


class PDFUploadChunker(PDFChunker):
    """
    A sibling chunker that lets users upload/select a PDF from ComfyUI's input
    directory, then returns the same outputs as PDFChunker.
    """

    @classmethod
    def _input_pdf_files(cls) -> list[str]:
        if folder_paths is None:
            return []

        input_dir = folder_paths.get_input_directory()
        if not os.path.isdir(input_dir):
            return []

        pdf_files = []
        for root, _, files in os.walk(input_dir):
            for filename in files:
                if not filename.lower().endswith(".pdf"):
                    continue
                rel_path = os.path.relpath(os.path.join(root, filename), input_dir)
                pdf_files.append(rel_path.replace(os.sep, "/"))

        return sorted(pdf_files)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pdf_file": (
                    cls._input_pdf_files(),
                    {
                        "pdf_upload": True,
                        "tooltip": "Upload or select a PDF from the ComfyUI input folder.",
                    },
                ),
                "chunk_size": ("INT", {"default": 4000, "min": 500, "max": 16000, "step": 100}),
                "overlap_size": ("INT", {"default": 400, "min": 0, "max": 8000, "step": 50}),
            }
        }

    RETURN_TYPES = ("CHUNKS", "STRING", "INT")
    RETURN_NAMES = ("chunks", "debug_text_output", "chunk_count")
    FUNCTION = "process_uploaded_pdf"
    CATEGORY = "Script To Video Suite"

    @staticmethod
    def _resolve_uploaded_pdf_path(pdf_file: str) -> str:
        if not pdf_file or not str(pdf_file).strip():
            raise ValueError("No PDF file selected. Upload or select a PDF first.")

        pdf_file = str(pdf_file).strip()
        input_dir = None
        if folder_paths is not None:
            input_dir = os.path.abspath(folder_paths.get_input_directory())

        if os.path.isabs(pdf_file):
            pdf_path = os.path.abspath(pdf_file)
        elif folder_paths is not None:
            pdf_path = os.path.abspath(folder_paths.get_annotated_filepath(pdf_file, input_dir))
        else:
            pdf_path = os.path.abspath(pdf_file)

        if input_dir is not None:
            try:
                if os.path.commonpath((input_dir, pdf_path)) != input_dir:
                    raise ValueError("Uploaded PDF must be inside the ComfyUI input folder.")
            except ValueError as exc:
                raise ValueError("Uploaded PDF must be inside the ComfyUI input folder.") from exc

        if not pdf_path.lower().endswith(".pdf"):
            raise ValueError(f"Selected file is not a PDF: {pdf_file}")

        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found at '{pdf_path}'")

        return pdf_path

    @classmethod
    def IS_CHANGED(cls, pdf_file, **kwargs):
        try:
            pdf_path = cls._resolve_uploaded_pdf_path(pdf_file)
            file_hash = hashlib.sha256()
            with open(pdf_path, "rb") as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    file_hash.update(chunk)
            return file_hash.hexdigest()
        except Exception:
            return float("NaN")

    @classmethod
    def VALIDATE_INPUTS(cls, pdf_file, **kwargs):
        try:
            cls._resolve_uploaded_pdf_path(pdf_file)
        except Exception as exc:
            return str(exc)
        return True

    def process_uploaded_pdf(self, pdf_file: str, chunk_size: int, overlap_size: int):
        pdf_path = self._resolve_uploaded_pdf_path(pdf_file)
        return self._process_pdf_path(pdf_path, chunk_size, overlap_size, "PDF Upload Chunker")
