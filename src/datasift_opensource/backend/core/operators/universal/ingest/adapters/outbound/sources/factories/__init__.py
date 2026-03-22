"""Factory for creating and discovering source adapters."""

from .source_factory import SourceAdapterFactory, register_source_adapter

__all__ = ["SourceAdapterFactory", "register_source_adapter"]
