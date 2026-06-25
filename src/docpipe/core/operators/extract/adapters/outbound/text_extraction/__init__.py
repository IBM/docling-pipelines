"""Text extraction adapters for the Extract operator.

This package contains adapters that implement different text extraction strategies:
- DoclingAdapter: Unified Docling library extraction (docling_library provider)
  Handles both standard Docling extraction and VLM extraction when use_vlm_pipeline is enabled
- DoclingServeAdapter: Remote extraction via Docling Serve API
"""

from docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_adapter import (
    DoclingAdapter,
)
from docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter import (
    DoclingServeAdapter,
)

__all__ = [
    "DoclingAdapter",
    "DoclingServeAdapter",
]
