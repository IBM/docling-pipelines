"""Domain models for document classification.

These models represent core domain concepts independent of any specific
LLM provider or infrastructure concerns.
"""

from dataclasses import dataclass

from docpipe.core.constants.operator_constants import OperatorConstants


@dataclass
class ClassificationRequest:
    """Request for document classification.

    Attributes:
        content: Document content to classify
        document_types: List of document types or dict with type descriptions
        max_content_length: Maximum content length to send to LLM
        confidence_threshold: Minimum confidence score for classification (1-10)
    """

    content: str
    document_types: list[str] | dict[str, str]
    max_content_length: int = 2000
    confidence_threshold: float = 7.0


@dataclass
class ClassificationResponse:
    """Response from document classification.

    Attributes:
        document_type: Classified document type
        confidence: Confidence score (1-10 scale)
        reasoning: Explanation for the classification decision
        success: Whether classification was successful
        error: Error message if classification failed
    """

    document_type: str
    confidence: float
    reasoning: str
    success: bool
    error: str | None = None


@dataclass
class ModelInfo:
    """Information about a classification model.

    Attributes:
        name: Model name
        provider: Provider name (e.g., 'ollama', 'watsonx')
        supports_json_mode: Whether model supports JSON output format
        max_tokens: Maximum token limit for the model
    """

    name: str
    provider: str
    supports_json_mode: bool = True
    max_tokens: int = 4096


def build_classification_prompt(*, request: ClassificationRequest) -> str:
    """Build the classification prompt for the LLM.

    This function creates a standardized prompt format that works across
    all LLM providers (Ollama, OpenAI, Watsonx, etc.).

    Args:
        request: Classification request with content and document types

    Returns:
        Formatted prompt string
    """
    if isinstance(request.document_types, dict):
        types_desc = "\n".join([f"- {name}: {desc}" for name, desc in request.document_types.items()])
    else:
        types_desc = "\n".join([f"- {document_type}" for document_type in request.document_types])

    sanitized_content = request.content[: request.max_content_length] if request.content else ""

    return f"""Classify the following document into one of these types:

{types_desc}

Document content:
{sanitized_content}

Respond with a JSON object containing:
- {OperatorConstants.Classification.FIELD_DOCUMENT_TYPE}: The document type that best matches (must be one of the types listed above)
- {OperatorConstants.Classification.FIELD_CONFIDENCE}: Confidence score from 1-10 (10 = certain)
- {OperatorConstants.Classification.FIELD_REASONING}: Brief explanation for why this document type was chosen

Example response:
{{
  "{OperatorConstants.Classification.FIELD_DOCUMENT_TYPE}": "invoice",
  "{OperatorConstants.Classification.FIELD_CONFIDENCE}": 9,
  "{OperatorConstants.Classification.FIELD_REASONING}": "Contains line items, totals, and payment terms typical of invoices"
}}"""
