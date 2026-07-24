"""Factory implementations for ACL adapters.

This package contains factory classes for creating ACL extraction adapters.
"""

from docpipe.core.operators.acl.adapters.outbound.factories.acl_adapter_factory import (
    ACLAdapterFactory,
    register_acl_adapter,
)

__all__ = [
    "ACLAdapterFactory",
    "register_acl_adapter",
]
