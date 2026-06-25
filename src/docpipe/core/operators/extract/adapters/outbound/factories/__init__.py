"""Factories for creating text extraction adapters.

This package contains factory classes for instantiating text extraction adapters
based on extraction provider and configuration.
"""

from .entity_extraction_adapter_factory import EntityExtractionAdapterFactory
from .text_extraction_adapter_factory import TextExtractionAdapterFactory

__all__ = [
    "EntityExtractionAdapterFactory",
    "TextExtractionAdapterFactory",
]
