import reflex as rx
from typing import TypedDict
import asyncio
import logging
import shutil
from pathlib import Path

# Configure logging to show in terminal with timestamp
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class FileInfo(TypedDict):
    name: str
    status: str
    progress: int
    size: str
    error: str


class ProcessedDoc(TypedDict):
    filename: str
    chunks: list[str]
    total_chars: int


async def process_document(file_path: Path, file_name: str) -> ProcessedDoc:
    """
    TODO: Placeholder for custom document processing logic.

    Expected interface:
    1. Input: Path to the saved file and its original filename.
    2. Logic:
       - Extract text (using libraries like pypdf, docx2txt, or OCR).
       - Optional: Generate embeddings and store in a vector database (Pinecone, Chroma, etc.).
       - Chunk the extracted text for retrieval-augmented generation (RAG).
    3. Return: A dictionary containing the filename, extracted chunks, and total character count.

    You can swap this implementation with your RAG pipeline entry point.
    """
    await asyncio.sleep(1.0)
    dummy_text = f"This is placeholder content extracted from {file_name}. " * 20
    chunk_size = 500
    chunks = [
        dummy_text[i : i + chunk_size] for i in range(0, len(dummy_text), chunk_size)
    ]
    return {"filename": file_name, "chunks": chunks, "total_chars": len(dummy_text)}


class FileUploadState(rx.State):
    """State management for file uploads and processing status."""

    files: list[FileInfo] = []
    processed_docs: list[ProcessedDoc] = []
    is_uploading: bool = False
    is_processing: bool = False
    processing_status: str = ""
    pipeline_ran: bool = False  # True after backend pipeline completes successfully

    def on_load(self):
        """Clear uploaded_files directory on page load/refresh."""
        try:
            upload_dir = rx.get_upload_dir()
            if upload_dir.exists():
                # Remove all files in the directory
                for file_path in upload_dir.iterdir():
                    if file_path.is_file():
                        file_path.unlink()
                        logger.info(f"Deleted file on page load: {file_path.name}")
                logger.info("Cleared uploaded_files directory on page load")
            # Reset ALL state — including in-flight flags so a reload always shows a clean UI
            self.files = []
            self.processed_docs = []
            self.processing_status = ""
            self.pipeline_ran = False
            self.is_processing = False
            self.is_uploading = False
        except Exception as e:
            logger.error(f"Error clearing uploaded_files on page load: {e}")

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        self.is_uploading = True
        # Reset processing status when new files are uploaded
        self.processing_status = ""
        yield
        upload_dir = rx.get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            file_name = file.name
            new_file: FileInfo = {
                "name": file_name,
                "status": "uploading",
                "progress": 10,
                "size": "Processing...",
                "error": "",
            }
            self.files.append(new_file)
            idx = len(self.files) - 1
            yield
            try:
                upload_data = await file.read()
                file_path = upload_dir / file_name
                with file_path.open("wb") as f:
                    f.write(upload_data)
                self.files[idx]["progress"] = 40
                self.files[idx]["status"] = "processing"
                yield
                doc_data = await process_document(file_path, file_name)
                if not doc_data["chunks"]:
                    self.files[idx]["status"] = "error"
                    self.files[idx]["error"] = "No text found in file"
                    yield
                    continue
                self.files[idx]["progress"] = 85
                yield
                self.processed_docs.append(doc_data)
                self.files[idx]["status"] = "complete"
                self.files[idx]["progress"] = 100
                self.files[idx]["size"] = f"{doc_data['total_chars']} chars"
            except Exception as e:
                logging.exception(f"Error processing file {file_name}: {e}")
                self.files[idx]["status"] = "error"
                self.files[idx]["error"] = str(e)
            yield
        self.is_uploading = False

    @rx.event
    def remove_file(self, name: str):
        # Remove physical file from disk
        upload_dir = rx.get_upload_dir()
        file_path = upload_dir / name
        try:
            if file_path.exists():
                file_path.unlink()
                logging.info(f"Deleted file from disk: {file_path}")
        except Exception as e:
            logging.error(f"Error deleting file {name}: {e}")
        
        # Remove from state
        self.files = [f for f in self.files if f["name"] != name]
        self.processed_docs = [d for d in self.processed_docs if d["filename"] != name]
        
        # Reset processing status when files are removed
        self.processing_status = ""

    @rx.event
    async def process_documents(self):
        """
        Trigger the datasift pipeline (flow_local.json) to process uploaded files
        by invoking the backend as a subprocess using its own .venv Python interpreter.
        
        Flow: ingest_local → extract_docling → docling_chunker → embeddings → opensearch
        """
        import subprocess
        self.is_processing = True
        self.processing_status = "Processing documents..."
        yield
        try:
            # Resolve paths relative to the project root
            project_root = Path(__file__).parents[6]
            print(f"Project root: {project_root}")
            backend_python = project_root / "src" / "datasift_opensource" / "backend" / ".venv" / "bin" / "python"
            orchestrator_script = project_root / "src" / "datasift_opensource" / "backend" / "core" / "orchestrator" / "cmdline" / "cmd_line_orchestrator.py"
            flow_file = project_root / "tests" / "flow_local.json"

            logger.info(f"Running backend pipeline: {orchestrator_script} --flow-file {flow_file}")

            proc = await asyncio.create_subprocess_exec(
                str(backend_python),
                str(orchestrator_script),
                "--flow-file", str(flow_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # merge stderr into stdout
                cwd=str(project_root / "src" / "datasift_opensource" / "backend"),
            )

            # Stream subprocess output line-by-line to the terminal in real-time
            async for line in proc.stdout:
                decoded = line.decode().rstrip()
                if decoded:
                    logger.info(f"[backend] {decoded}")

            await proc.wait()

            if proc.returncode == 0:
                logger.info("Pipeline completed successfully")
                self.processing_status = "Documents processed successfully!"
                self.pipeline_ran = True
            else:
                logger.error(f"Pipeline exited with code {proc.returncode}")
                self.processing_status = f"Error: Pipeline exited with code {proc.returncode}"
                self.pipeline_ran = False
        except Exception as e:
            logger.error(f"Error processing documents: {e}")
            self.processing_status = f"Error: {str(e)}"
        finally:
            self.is_processing = False
        yield

    @rx.var
    def has_files(self) -> bool:
        return len(self.files) > 0

    @rx.var
    def total_chunks(self) -> int:
        return sum((len(doc["chunks"]) for doc in self.processed_docs))

    @rx.var
    def total_docs_ready(self) -> int:
        return len(self.processed_docs)