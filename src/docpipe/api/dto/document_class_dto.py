"""Document class API response Data Transfer Objects (DTOs).

Defines the Pydantic response model returned by the
``GET /api/v1/document_classes`` endpoint.
"""

from pydantic import BaseModel, Field


class DocumentClassItem(BaseModel):
    """Metadata for a single document class.

    Attributes:
        document_type: Machine-readable type identifier (e.g. ``"Invoice"``).
        document_description: Human-readable description of the document class.

    Example:
        >>> item = DocumentClassItem(
        ...     document_type="Invoice",
        ...     document_description="An invoice is a financial document ...",
        ... )
    """

    document_type: str = Field(
        description="Machine-readable document type identifier",
        examples=["Invoice", "Passport", "Bank Statement"],
    )
    document_description: str = Field(
        description="Human-readable description of the document class",
        examples=["An invoice is a financial document issued by a seller to a buyer ..."],
    )
