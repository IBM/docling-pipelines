"""Outbound adapters for ACL extraction.

This package contains outbound adapter implementations for various
ACL providers (SharePoint, S3, Google Drive, etc.).
"""

# Import adapters to trigger registration
from docpipe.core.operators.acl.adapters.outbound import sharepoint_adapter  # noqa: F401
from docpipe.core.operators.acl.adapters.outbound.factories.acl_adapter_factory import (
    ACLAdapterFactory,
    register_acl_adapter,
)

__all__ = [
    "ACLAdapterFactory",
    "register_acl_adapter",
]
