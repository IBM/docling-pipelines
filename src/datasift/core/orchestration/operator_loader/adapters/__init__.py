"""Adapters for loading operators from various sources."""

# Import adapters to trigger decorator registration
from datasift.core.orchestration.operator_loader.adapters import (
    filesystem_adapter,
    s3_adapter,
)

__all__ = ["filesystem_adapter", "s3_adapter"]
