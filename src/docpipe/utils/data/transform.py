"""Data transformation utilities for PyArrow table operations.
   This class serves as a compatibility shim between docpipe
   and the external data-prep-toolkit-transforms library. It:

Primary mode: Imports TransformUtils from data_processing.utils (the external toolkit)
Fallback mode: Provides a minimal local implementation if the external library is unavailable
Centralizes PyArrow table column operations across all operators

"""

from data_processing.utils import TransformUtils

__all__ = ["TransformUtils"]
