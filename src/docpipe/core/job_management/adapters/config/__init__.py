"""
Configuration and Dependency Injection

This module provides factory classes for creating and wiring job management
components with proper dependency injection.
"""

from .job_management_factory import (
    FrameworkType,
    JobManagementFactory,
    StorageBackend,
    get_default_factory,
    reset_default_factory,
)
from .report_storage_factory import (
    ContentStorageFactory,
    get_report_storage,
    register_content_storage,
    reset_report_storage,
)

__all__ = [
    "ContentStorageFactory",
    "FrameworkType",
    "JobManagementFactory",
    "StorageBackend",
    "get_default_factory",
    "get_report_storage",
    "register_content_storage",
    "reset_default_factory",
    "reset_report_storage",
]
