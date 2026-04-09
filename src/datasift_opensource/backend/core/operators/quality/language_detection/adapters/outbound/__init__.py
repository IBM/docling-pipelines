"""Outbound adapters for language detection services.

This module imports all adapters to trigger their auto-registration
with the LanguageAdapterFactory via the @register_language_adapter decorator.
"""

# Import adapters to trigger registration
from .fasttext_adapter import FastTextAdapter
from .langdetect_adapter import LangdetectAdapter

__all__ = [
    "FastTextAdapter",
    "LangdetectAdapter",
]
