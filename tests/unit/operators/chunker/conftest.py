"""Shared fixtures and module-level setup for ChunkerOperator tests.

The langchain_experimental mock must be installed before any chunker import
to avoid optional-dependency ImportErrors during collection.
"""

import sys
from unittest.mock import Mock

# Patch langchain_experimental at collection time so every test module that
# imports ChunkerOperator does not need its own guard.
if "langchain_experimental" not in sys.modules:
    sys.modules["langchain_experimental"] = Mock()
    sys.modules["langchain_experimental.text_splitter"] = Mock()
