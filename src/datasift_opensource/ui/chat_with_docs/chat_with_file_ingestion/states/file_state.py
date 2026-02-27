import reflex as rx
from typing import TypedDict
import asyncio
import logging
from pathlib import Path


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

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        self.is_uploading = True
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
        self.files = [f for f in self.files if f["name"] != name]
        self.processed_docs = [d for d in self.processed_docs if d["filename"] != name]

    @rx.var
    def has_files(self) -> bool:
        return len(self.files) > 0

    @rx.var
    def total_chunks(self) -> int:
        return sum((len(doc["chunks"]) for doc in self.processed_docs))

    @rx.var
    def total_docs_ready(self) -> int:
        return len(self.processed_docs)