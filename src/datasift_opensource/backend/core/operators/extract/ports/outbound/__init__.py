"""Outbound port interfaces for extract operators."""

from core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort
from core.operators.extract.ports.outbound.text_extraction import TextExtractionPort

__all__ = ["EntityExtractionPort", "TextExtractionPort"]
