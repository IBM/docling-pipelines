import json
import reflex as rx
from typing import TypedDict
import asyncio
import logging
import shutil
import tempfile
import os
from pathlib import Path

# Configure logging to show in terminal with timestamp
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Shared log file path — written by process_documents, polled by LogPollerState
# Stored inside the UI repo so it's easy to inspect alongside the app.
_UI_ROOT = Path(__file__).parents[3]  # .../chat_with_docs/
_LOG_DIR = _UI_ROOT / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "datasift_pipeline.log"


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


class LogPollerState(rx.State):
    """
    Polls the pipeline log file every second and exposes log lines to the UI.
    Also owns the log tearsheet visibility (show_logs) — kept here rather than
    ThemeState so all log-related state is co-located.
    Runs as a background task so it never blocks FileUploadState's event lock.
    """

    log_lines: list[str] = []
    show_logs: bool = False  # Controls log tearsheet overlay visibility
    _polling: bool = False

    @rx.event
    def open_logs(self):
        self.show_logs = True

    @rx.event
    def close_logs(self):
        self.show_logs = False

    @rx.event(background=True)
    async def start_polling(self):
        """
        Start polling the log file. Runs in background — does not block other events.
        Always clears the log file and resets log_lines before starting so a second
        run never shows stale output from the previous run.
        """
        # Clear the log file and reset state BEFORE starting the poll loop.
        # This must happen here (not in process_documents) because start_polling
        # fires first; if the old file still contains PIPELINE_DONE the loop would
        # exit immediately on the first iteration.
        try:
            _LOG_FILE.write_text("", encoding="utf-8")
        except Exception:
            pass

        async with self:
            self._polling = True
            self.log_lines = []

        try:
            while True:
                async with self:
                    # Read the log file and update log_lines
                    done = False
                    if _LOG_FILE.exists():
                        try:
                            text = _LOG_FILE.read_text(
                                encoding="utf-8", errors="replace"
                            )
                            all_lines = text.splitlines()
                            # Filter out the sentinel line from display
                            visible = [
                                l
                                for l in all_lines
                                if l.strip() and "PIPELINE_DONE" not in l
                            ]
                            self.log_lines = visible
                            # Stop polling when sentinel appears
                            done = any("PIPELINE_DONE" in l for l in all_lines)
                        except Exception:
                            pass

                    if done:
                        self._polling = False
                        break

                await asyncio.sleep(1.0)
        except Exception as e:
            logger.error(f"LogPollerState polling error: {e}")
            async with self:
                self._polling = False

    @rx.event
    def clear_logs(self):
        self.log_lines = []
        self.show_logs = False
        self._polling = False
        try:
            if _LOG_FILE.exists():
                _LOG_FILE.unlink()
        except Exception:
            pass


class FileUploadState(rx.State):
    """State management for file uploads and processing status."""

    files: list[FileInfo] = []
    processed_docs: list[ProcessedDoc] = []
    is_uploading: bool = False
    is_processing: bool = False
    processing_status: str = ""
    processing_failed: bool = False  # True when pipeline exits with error
    pipeline_ran: bool = False  # True after backend pipeline completes successfully
    datasift_index: str = ""  # Index name extracted from flow JSON

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
            self.processing_failed = False
            self.pipeline_ran = False
            self.is_processing = False
            self.is_uploading = False
            # Clear the log file on page load
            try:
                if _LOG_FILE.exists():
                    _LOG_FILE.unlink()
            except Exception:
                pass
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

    @rx.event(background=True)
    async def process_documents(self):
        """
        Trigger the datasift pipeline (flow_invoice_entities_expanded.json) to process
        uploaded files by invoking the backend as a subprocess using its own .venv Python
        interpreter.

        The OpenSearch index name is taken from the DATASIFT_INDEX environment variable
        (default: "invoices_entities_expanded_test") so that the same index name is used
        for both ingestion (here) and querying (chat_state.py / query_runner.py).

        Runs as a background task so the state lock is released between updates,
        allowing ThemeState.open_logs and LogPollerState to respond while running.
        Logs are written to _LOG_FILE which LogPollerState polls every second.
        Flow: ingest_local → extract_docling → extract_entities_ollama → docling_chunker → embeddings → opensearch
        """
        async with self:
            self.is_processing = True
            self.processing_failed = False
            self.processing_status = "Processing documents..."

        # Give start_polling a moment to clear the log file before we start writing.
        # Both are background tasks fired in order; this tiny yield ensures the file
        # is empty before the pipeline subprocess begins appending to it.
        await asyncio.sleep(0.3)

        tmp_flow_path: Path | None = None  # track temp file for cleanup in finally
        try:
            # Resolve paths relative to the project root
            project_root = Path(__file__).parents[6]
            logger.info(f"Project root: {project_root}")
            backend_python = (
                project_root
                / "src"
                / "datasift_opensource"
                / "backend"
                / ".venv"
                / "bin"
                / "python"
            )
            orchestrator_script = (
                project_root
                / "src"
                / "datasift_opensource"
                / "backend"
                / "core"
                / "orchestrator"
                / "cmdline"
                / "cmd_line_orchestrator.py"
            )
            base_flow_file = project_root / "tests" / "flow_invoice_entities.json"

            # ----------------------------------------------------------------
            # Extract the index_name from the flow JSON's OpenSearch node.
            # This ensures the index created by the pipeline is the same one
            # queried by chat_state / query_runner.
            # ----------------------------------------------------------------
            with base_flow_file.open("r", encoding="utf-8") as fh:
                flow_data = json.load(fh)

            # The flow JSON may be wrapped under a top-level "flow" key
            flow_def = flow_data.get("flow", flow_data)
            datasift_index = None
            for node in flow_def.get("dag", []):
                if node.get("operator") == "opensearch":
                    datasift_index = node["config"].get("index_name")
                    logger.info(
                        f"Using index_name from flow JSON: '{datasift_index}'"
                    )
                    break
            
            # Fallback if no OpenSearch node found
            if not datasift_index:
                datasift_index = "datasift_documents"
                logger.warning(
                    f"No OpenSearch node found in flow JSON, using default: '{datasift_index}'"
                )
            
            # Store the index name in state so chat_state can access it
            async with self:
                self.datasift_index = datasift_index

            # Write the patched definition to a temp file so the orchestrator
            # can load it without modifying the original flow JSON on disk.
            tmp_flow = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                prefix="datasift_flow_",
                delete=False,
                encoding="utf-8",
            )
            json.dump(flow_data, tmp_flow, indent=2)
            tmp_flow.flush()
            tmp_flow.close()
            flow_file = Path(tmp_flow.name)
            tmp_flow_path = flow_file  # record for cleanup

            logger.info(
                f"Running backend pipeline: {orchestrator_script} --flow-file {flow_file} "
                f"(index: {datasift_index})"
            )

            # Stream subprocess output: write to log file AND echo to terminal via logger
            proc = await asyncio.create_subprocess_exec(
                str(backend_python),
                str(orchestrator_script),
                "--flow-file",
                str(flow_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # merge stderr into stdout
                cwd=str(
                    project_root
                ),  # run from project root so flow file path resolves correctly
            )

            # Collect all output lines so we can scan for errors after completion
            output_lines: list[str] = []
            assert proc.stdout is not None  # guaranteed when stdout=PIPE
            with _LOG_FILE.open("w", encoding="utf-8", buffering=1) as log_fh:
                async for raw_line in proc.stdout:
                    line = raw_line.decode(errors="replace").rstrip()
                    if line:
                        logger.info(f"[pipeline] {line}")  # echo to terminal
                        log_fh.write(line + "\n")
                        log_fh.flush()
                        output_lines.append(line)

            await proc.wait()

            # Detect errors even when exit code is 0 — the orchestrator logs errors
            # but may still exit cleanly (e.g. Ollama connection failure in embeddings).
            _ERROR_PATTERNS = (
                "ERROR",
                "Failed to connect",
                "failed to generate",
                "Exception",
                "Traceback",
            )
            has_errors_in_log = any(
                any(pat.lower() in line.lower() for pat in _ERROR_PATTERNS)
                for line in output_lines
            )

            if proc.returncode != 0:
                logger.error(f"Pipeline exited with code {proc.returncode}")
                async with self:
                    self.processing_status = f"Pipeline failed (exit code {proc.returncode}). Check logs for details."
                    self.processing_failed = True
                    self.pipeline_ran = (
                        True  # allow chat — partial results may be in OpenSearch
                    )
            elif has_errors_in_log:
                logger.warning("Pipeline exited 0 but errors were detected in output")
                async with self:
                    self.processing_status = (
                        "Pipeline completed with errors. Check logs for details."
                    )
                    self.processing_failed = True
                    self.pipeline_ran = (
                        True  # allow chat — partial results may be in OpenSearch
                    )
            else:
                logger.info("Pipeline completed successfully")
                async with self:
                    self.processing_status = "Documents processed successfully!"
                    self.processing_failed = False
                    self.pipeline_ran = True
        except Exception as e:
            logger.error(f"Error processing documents: {e}")
            async with self:
                self.processing_status = f"Error: {str(e)}"
                self.processing_failed = True
        finally:
            async with self:
                self.is_processing = False
            # Write sentinel so LogPollerState stops polling
            try:
                with _LOG_FILE.open("a", encoding="utf-8") as f:
                    f.write("\nPIPELINE_DONE\n")
            except Exception:
                pass
            # Clean up the temporary patched flow file
            try:
                if tmp_flow_path is not None and tmp_flow_path.exists():
                    tmp_flow_path.unlink()
            except Exception:
                pass

    @rx.var
    def has_files(self) -> bool:
        return len(self.files) > 0

    @rx.var
    def total_chunks(self) -> int:
        return sum((len(doc["chunks"]) for doc in self.processed_docs))

    @rx.var
    def total_docs_ready(self) -> int:
        return len(self.processed_docs)
