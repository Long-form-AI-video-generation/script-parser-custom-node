
import os
import hashlib
from importlib import metadata
try:
    import pymupdf as fitz
except ImportError:
    import fitz  
try:
    from docling.document_converter import DocumentConverter
except ImportError:
    DocumentConverter = None

try:
    import folder_paths
except ImportError:
    folder_paths = None

class ScriptChunks(list):
    """List of script chunks with source PDF metadata attached."""

    def __init__(self, chunks, source_page_count: int = 0):
        super().__init__(chunks)
        self.source_page_count = source_page_count

class PDFChunker:
    
    
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

    @staticmethod
    def _accelerate_diagnostics() -> str:
        try:
            version = metadata.version("accelerate")
        except metadata.PackageNotFoundError:
            return "Detected accelerate: not installed"

        try:
            import accelerate
            import accelerate.utils.memory as accelerate_memory

            has_clear_device_cache = hasattr(accelerate_memory, "clear_device_cache")
            return (
                f"Detected accelerate {version} at {accelerate.__file__}; "
                f"clear_device_cache available: {has_clear_device_cache}"
            )
        except Exception as exc:
            return f"Detected accelerate {version}, but importing it failed: {exc}"

    @staticmethod
    def _extract_with_pymupdf(pdf_path: str) -> str:
        with fitz.open(pdf_path) as pdf:
            pages = [page.get_text("text", sort=True).strip() for page in pdf]
        text = "\n\n".join(page for page in pages if page)
        if not text.strip():
            raise IOError("PyMuPDF found no extractable text in the PDF.")
        return text

    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at '{pdf_path}'")

        if DocumentConverter is None:
            print("PDF Chunker: Docling is not installed; using PyMuPDF text extraction.")
            return self._extract_with_pymupdf(pdf_path)

        try:
            converter = DocumentConverter()
            result = converter.convert(pdf_path)
            markdown_output = result.document.export_to_markdown()
            return markdown_output
        except Exception as e:
            error_text = str(e)
            print(
                "PDF Chunker: Docling extraction failed; falling back to PyMuPDF. "
                f"Reason: {error_text}"
            )
            return self._extract_with_pymupdf(pdf_path)

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

    @staticmethod
    def _get_pdf_page_count(pdf_path: str) -> int:
        try:
            with fitz.open(pdf_path) as pdf:
                return pdf.page_count
        except Exception as exc:
            print(f"Could not read PDF page count ({exc}); panel density will use text length.")
            return 0

    def _process_pdf_path(self, pdf_path: str, chunk_size: int, overlap_size: int, node_name: str):
        print(f"Executing '{node_name}' node...")

        raw_text = self._extract_text_from_pdf(pdf_path)
        page_count = self._get_pdf_page_count(pdf_path)
        script_chunks = ScriptChunks(
            self._chunk_text(raw_text, chunk_size, overlap_size),
            source_page_count=page_count,
        )
        chunk_count = len(script_chunks)

        if page_count > 0:
            print(f"PDF processed into {chunk_count} chunks from {page_count} page(s).")
        else:
            print(f"PDF processed into {chunk_count} chunks.")

        # Create the debug string for visual inspection in other nodes
        debug_text = f"Total Chunks: {chunk_count}\n\n"
        debug_text += "\n\n--- CHUNK BREAK ---\n\n".join(script_chunks)

        # Return the list of chunks, the debug text, and the count
        return (script_chunks, debug_text, chunk_count)

    def process_pdf(self, pdf_path: str, chunk_size: int, overlap_size: int):
        return self._process_pdf_path(pdf_path, chunk_size, overlap_size, "PDF Chunker")


class PDFUploadChunker(PDFChunker):
 
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
