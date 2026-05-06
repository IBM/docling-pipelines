"""
Transformation functions for entity curation.

This module provides a registry of transformation functions that can be applied
to entity values during the curation process.

Includes 4 core transformation functions:
- currency_to_numeric
- make_date_uniform
- to_number
- weight_to_numeric
"""

from .currency_to_numeric import currency_to_numeric
from .make_date_uniform import make_date_uniform
from .to_number import to_number
from .weight_to_numeric import weight_to_numeric

__all__ = [
    "TRANSFORMS",
    "currency_to_numeric",
    "make_date_uniform",
    "to_number",
    "weight_to_numeric",
]

# Transform function registry
# Maps transform names to their corresponding functions
TRANSFORMS = {name: globals()[name] for name in __all__ if name != "TRANSFORMS"}
