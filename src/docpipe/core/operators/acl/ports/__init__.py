"""Ports layer for ACL extraction.

This package contains the port interfaces that define the contracts
between the domain layer and external adapters.
"""

from docpipe.core.operators.acl.ports.outbound.acl_extraction import (
    ACLExtractionPort,
)

__all__ = [
    "ACLExtractionPort",
]
