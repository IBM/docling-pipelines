"""Outbound adapters for text extraction.

This module contains concrete implementations of the TextExtractionPort interface.
Each adapter implements a specific extraction strategy:

- DoclingAdapter: Unified Docling library extraction (docling_library provider)
  Handles both standard Docling extraction and VLM extraction when use_vlm_pipeline is enabled
- DoclingServeAdapter: Remote extraction via Docling Serve API

All adapters follow hexagonal architecture principles, implementing only the
extraction logic while the port handles orchestration and parallel processing.

The TextExtractionAdapterFactory provides a convenient way to create adapters
based on extraction provider and configuration.
"""

from docpipe.core.operators.extract.adapters.outbound.factories.text_extraction_adapter_factory import (
    TextExtractionAdapterFactory,
)
from docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_adapter import DoclingAdapter
from docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter import DoclingServeAdapter

__all__ = [
    "DoclingAdapter",
    "DoclingServeAdapter",
    "TextExtractionAdapterFactory",
]
