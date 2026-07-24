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

__all__ = [
    "FrameworkType",
    "JobManagementFactory",
    "StorageBackend",
    "get_default_factory",
    "reset_default_factory",
]
