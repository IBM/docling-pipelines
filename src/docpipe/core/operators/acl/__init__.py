"""ACL (Access Control List) operator package.

This package provides ACL extraction capabilities for various providers
(SharePoint, S3, Google Drive, etc.) following hexagonal architecture principles.
"""

from docpipe.core.operators.acl.acl_operator import ACLOperator
from docpipe.core.operators.acl.adapters.outbound.factories.acl_adapter_factory import (
    ACLAdapterFactory,
    register_acl_adapter,
)
from docpipe.core.operators.acl.domain.models import (
    ACLExtractionResult,
    ACLRequest,
    ACLResponse,
    RawPermission,
)
from docpipe.core.operators.acl.ports.outbound.acl_extraction import (
    ACLExtractionPort,
)

__all__ = [
    "ACLAdapterFactory",
    "ACLExtractionPort",
    "ACLExtractionResult",
    "ACLOperator",
    "ACLRequest",
    "ACLResponse",
    "RawPermission",
    "register_acl_adapter",
]
