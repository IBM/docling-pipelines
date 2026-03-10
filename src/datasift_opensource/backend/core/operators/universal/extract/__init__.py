"""Extract operators for document content extraction."""

from core.operators.universal.extract.extract_docling import ExtractDoclingOperator
from core.operators.universal.extract.extract_entities_ollama import (
    ExtractEntitiesOllamaOperator,
)

__all__ = ["ExtractDoclingOperator", "ExtractEntitiesOllamaOperator"]
