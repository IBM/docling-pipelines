"""Outbound port interfaces for extract operators."""

from docpipe.core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort
from docpipe.core.operators.extract.ports.outbound.text_extraction import TextExtractionPort

__all__ = ["EntityExtractionPort", "TextExtractionPort"]
