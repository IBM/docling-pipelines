from typing import AsyncGenerator, List
import aiohttp
import json

from core.operators.ingest.ports.outbound.document_source import DocumentSourcePort
from core.operators.ingest.domain.models import Document
from core.operators.ingest.adapters.outbound.sources.factories.source_factory import register_source_adapter
from .config import DatabricksConfig

@register_source_adapter("databricks")
class DatabricksSourceAdapter(DocumentSourcePort):
    """
    Adapter for ingesting documents from Databricks using LangChain.
    This adapter wraps LangChain's DatabricksLoader to provide a simpler,
    more maintainable implementation with automatic OAuth2 handling and
    Google Workspace file export. 
    """

    SOURCE_NAME = "databricks"
    SOURCE_DISPLAY_NAME = "Databricks"
    CONFIG_CLASS = DatabricksConfig

    def __init__(self):
        """Initialize the adapter."""
        pass


    async def fetch_documents(
        self, config: DatabricksConfig
    ) -> AsyncGenerator[Document, None]:
        """Fetch documents from Databricks."""
        try:
            file_types: None = None

        except Exception as e:
            raise e
