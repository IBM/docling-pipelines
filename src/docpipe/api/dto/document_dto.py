"""Data Transfer Objects for document retrieval API."""

from typing import Any

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    """Response model for document retrieval."""

    id: str = Field(..., description="Document ID")
    content: str = Field(..., description="Document content")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata",
    )
    created_at: str | None = Field(None, description="Creation timestamp")
    updated_at: str | None = Field(None, description="Last update timestamp")

    @classmethod
    def from_opensearch_hit(cls, *, hit: dict[str, Any]) -> "DocumentResponse":
        """Convert OpenSearch hit to DocumentResponse.

        Args:
            hit: OpenSearch hit dictionary

        Returns:
            DocumentResponse instance
        """
        source = hit.get("_source", {})
        # Support both 'content' and 'text' fields (VectorDB operator uses 'text' via feature_mappings)
        content = source.get("content") or source.get("text", "")
        return cls(
            id=hit.get("_id", ""),
            content=content,
            metadata=source.get("metadata", {}),
            created_at=source.get("created_at"),
            updated_at=source.get("updated_at"),
        )


class DocumentSearchRequest(BaseModel):
    """Request model for document search."""

    query: str | None = Field(
        None,
        description="Full-text search query across content, title, and metadata",
        examples=["machine learning"],
    )
    filters: dict[str, Any] | None = Field(
        None,
        description="Field filters for exact matching",
        examples=[{"category": "tech", "status": "published"}],
    )
    sort: list[dict[str, str]] | None = Field(
        None,
        description="Sort specification with field and direction",
        examples=[[{"created_at": "desc"}, {"title": "asc"}]],
    )
    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum number of results per page",
        examples=[20],
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of results to skip for pagination",
        examples=[0],
    )


class DocumentSearchResponse(BaseModel):
    """Response model for document search."""

    documents: list[DocumentResponse] = Field(
        ...,
        description="List of documents matching the search criteria",
    )
    total: int = Field(
        ...,
        description="Total number of documents matching the query",
    )
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Current offset")
    has_more: bool = Field(
        ...,
        description="Whether there are more results available",
    )

    @classmethod
    def from_opensearch_response(
        cls,
        *,
        response: dict[str, Any],
        limit: int,
        offset: int,
    ) -> "DocumentSearchResponse":
        """Convert OpenSearch response to DocumentSearchResponse.

        Args:
            response: OpenSearch search response
            limit: Results per page
            offset: Current offset

        Returns:
            DocumentSearchResponse instance
        """
        hits = response.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        documents = [DocumentResponse.from_opensearch_hit(hit=hit) for hit in hits.get("hits", [])]

        return cls(
            documents=documents,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(documents)) < total,
        )
