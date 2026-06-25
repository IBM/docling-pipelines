"""Adapters for loading operators from various sources."""

# Import adapters to trigger decorator registration
from docpipe.core.orchestration.operator_loader.adapters import (
    filesystem_adapter,
    package_adapter,
    s3_adapter,
)

__all__ = ["filesystem_adapter", "package_adapter", "s3_adapter"]
