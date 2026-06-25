"""Box source adapter for document ingestion."""

try:
    from .adapter import BoxSourceAdapter
    from .config import BoxSourceConfig

    __all__ = ["BoxSourceAdapter", "BoxSourceConfig"]
except ImportError:
    # Box SDK dependencies not installed
    __all__ = []
