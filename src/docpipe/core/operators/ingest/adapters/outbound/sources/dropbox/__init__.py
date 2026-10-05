"""Dropbox source adapter for document ingestion."""

try:
    from .adapter import DropboxSourceAdapter
    from .config import DropboxSourceConfig

    __all__ = ["DropboxSourceAdapter", "DropboxSourceConfig"]
except ImportError:
    # Dropbox SDK dependencies not installed
    __all__ = []
