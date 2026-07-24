"""Outbound ports for ACL extraction.

This package contains outbound port interfaces for ACL extraction,
defining contracts for external service integrations.
"""

from docpipe.core.operators.acl.ports.outbound.acl_extraction import (
    ACLExtractionPort,
)

__all__ = [
    "ACLExtractionPort",
]
