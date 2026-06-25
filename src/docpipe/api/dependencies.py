"""
Application-level dependency providers for FastAPI.

This module provides dependency injection for job management services
and other application-level components.
"""

from functools import lru_cache

from docpipe.core.job_management.adapters.config.job_management_factory import get_default_factory
from docpipe.core.job_management.application.services import JobManagementService
from docpipe.core.job_management.domain.ports import JobStatsService


@lru_cache(maxsize=1)
def get_job_stats_service() -> JobStatsService:
    """
    Dependency provider for job stats service (singleton).

    Returns:
        JobStatsService: Configured service instance (cached singleton)
    """
    factory = get_default_factory()
    return factory.create_job_stats_service()


@lru_cache(maxsize=1)
def get_job_management_service() -> JobManagementService:
    """
    Dependency provider for job management service (singleton).

    Returns:
        JobManagementService: Configured service instance (cached singleton)
    """
    factory = get_default_factory()
    return factory.create_job_management_service()
