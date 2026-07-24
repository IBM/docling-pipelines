"""Adapters layer for ACL extraction.

This package contains adapter implementations that connect the domain
layer to external services and providers.
"""

from docpipe.core.operators.acl.adapters.outbound.factories.acl_adapter_factory import (
    ACLAdapterFactory,
    register_acl_adapter,
)

__all__ = [
    "ACLAdapterFactory",
    "register_acl_adapter",
]
