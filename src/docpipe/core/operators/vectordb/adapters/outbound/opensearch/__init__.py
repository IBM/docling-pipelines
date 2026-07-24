"""OpenSearch vector database adapter components."""

from docpipe.core.operators.vectordb.adapters.outbound.opensearch.adapter import OpenSearchAdapter
from docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor import OpenSearchBatchProcessor
from docpipe.core.operators.vectordb.adapters.outbound.opensearch.client import OpenSearchClient
from docpipe.core.operators.vectordb.adapters.outbound.opensearch.index_manager import OpenSearchIndexManager

__all__ = [
    "OpenSearchAdapter",
    "OpenSearchBatchProcessor",
    "OpenSearchClient",
    "OpenSearchIndexManager",
]
