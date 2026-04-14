"""Domain models for vector database operations.

These models represent core domain concepts independent of any specific
vector database provider or infrastructure concerns.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class IndexRequest:
    """Request for indexing documents in vector database.

    Attributes:
        documents: List of (doc_id, document_dict) tuples to index
        index_name: Name of the index
        create_index: Whether to create index if it doesn't exist
    """

    documents: list[tuple[str, dict[str, Any]]]
    index_name: str
    create_index: bool = True


@dataclass
class IndexResult:
    """Result from indexing operation.

    Attributes:
        success_count: Number of successfully indexed documents
        failed_count: Number of failed documents
        failed_items: List of failed document details
        batch_count: Number of batches processed
    """

    success_count: int
    failed_count: int
    failed_items: list[dict[str, Any]]
    batch_count: int = 0


@dataclass
class QueryRequest:
    """Request for querying documents.

    Attributes:
        doc_names: List of document names to query
        fields: Optional list of fields to return
        index_name: Name of the index to query
    """

    doc_names: list[str]
    fields: list[str] | None
    index_name: str


@dataclass
class QueryResult:
    """Result from query operation.

    Attributes:
        documents: List of matching documents
        count: Number of documents found
    """

    documents: list[dict[str, Any]]
    count: int


@dataclass
class DeleteRequest:
    """Request for deleting documents.

    Attributes:
        doc_ids: List of document IDs to delete
        index_name: Name of the index
    """

    doc_ids: list[str]
    index_name: str


@dataclass
class DeleteResult:
    """Result from delete operation.

    Attributes:
        success_count: Number of successfully deleted documents
        failed_count: Number of failed deletions
    """

    success_count: int
    failed_count: int


@dataclass
class IndexInfo:
    """Information about a vector database index.

    Attributes:
        name: Index name
        dimension: Vector dimension
        document_count: Number of documents in index
        engine: KNN engine type (e.g., 'faiss', 'nmslib')
        exists: Whether the index exists
    """

    name: str
    dimension: int | None
    document_count: int
    engine: str | None
    exists: bool
