"""Utility functions for document set API routes.

This module contains helper functions for converting domain models to DTOs
and serializing data for API responses.
"""

from datetime import UTC, datetime
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]

from docpipe.api.dto.document_set_dto import (
    DocumentSetPreviewResponse,
    DocumentSetResponse,
)
from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet


def document_set_to_response(*, document_set: DocumentSet) -> DocumentSetResponse:
    """Convert a domain document set into an API response DTO.

    Args:
        document_set: Domain model document set

    Returns:
        DocumentSetResponse DTO
    """
    created_at = document_set.created_at or datetime.now(UTC)
    updated_at = document_set.updated_at or created_at

    return DocumentSetResponse(
        id=document_set.id or "",
        name=document_set.name,
        description=document_set.description,
        storage_backend=document_set.storage_backend,
        database_path=document_set.database_path,
        table_name=document_set.table_name,
        total_documents=document_set.total_documents,
        total_size_bytes=document_set.total_size_bytes,
        total_pages=document_set.total_pages,
        created_at=created_at,
        updated_at=updated_at,
        metadata=document_set.metadata or {},
    )


def make_json_serializable(*, value: Any) -> Any:
    """Convert preview values into JSON-serializable primitives.

    Args:
        value: Value to convert

    Returns:
        JSON-serializable representation of the value
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): make_json_serializable(value=val) for key, val in value.items()}
    if isinstance(value, list):
        return [make_json_serializable(value=item) for item in value]
    if isinstance(value, tuple):
        return [make_json_serializable(value=item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def table_to_preview_response(*, table: pa.Table) -> DocumentSetPreviewResponse:
    """Convert a PyArrow table into a preview DTO.

    Args:
        table: PyArrow table to convert

    Returns:
        DocumentSetPreviewResponse DTO
    """
    rows = table.to_pylist()
    serialized_rows = [{column: make_json_serializable(value=value) for column, value in row.items()} for row in rows]
    return DocumentSetPreviewResponse(
        columns=table.column_names,
        data=serialized_rows,
        total_rows=table.num_rows,
    )
