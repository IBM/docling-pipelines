"""LangChain-compatible loader wrapper for OneDrive adapter."""
import asyncio
from typing import Iterator
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from .adapter import OneDriveSourceAdapter
from .config import OneDriveSourceConfig


class OneDriveDirectoryLoader(BaseLoader):
    """LangChain BaseLoader wrapper for OneDrive adapter."""
    
    def __init__(
        self,
        drive_id: str | None,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        folder_path: str | None = None,
        recursive: bool = True,
        **kwargs
    ):
        self.config = OneDriveSourceConfig(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            drive_id=drive_id,
            folder_path=folder_path,
            recursive=recursive,
        )
        self.adapter = OneDriveSourceAdapter()
    
    def load(self) -> list[Document]:
        """Load documents synchronously."""
        return asyncio.run(self._async_load())
    
    async def _async_load(self) -> list[Document]:
        """Load documents asynchronously."""
        documents = []
        async for adapter_doc in self.adapter.fetch_documents(self.config):
            langchain_doc = Document(
                page_content="",  # Keep empty, binary content stored separately
                metadata={
                    "source": adapter_doc.source_url,
                    "name": adapter_doc.name,
                    "id": adapter_doc.id,
                    "last_modified": adapter_doc.modified_time.timestamp() if adapter_doc.modified_time else 0,
                    "size": adapter_doc.size,
                    "mimetype": adapter_doc.mimetype,
                    "has_binary_content": True,
                    **adapter_doc.metadata,
                }
            )
            # Store binary content as attribute for downstream processing
            langchain_doc._binary_content = adapter_doc.content
            documents.append(langchain_doc)
        return documents
    
    def lazy_load(self) -> Iterator[Document]:
        """Lazy load not implemented - use load() instead."""
        return iter(self.load())
