"""
Application-level dependency providers for FastAPI.

This module provides dependency injection for job management services
and other application-level components.
"""

from functools import lru_cache

from fastapi import Depends

from docpipe.core.assets.flows.adapters.config import RepositoryFactory
from docpipe.core.assets.flows.application.services import FlowService
from docpipe.core.assets.flows.domain.ports import FlowRepository
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
def get_flow_repository() -> FlowRepository:
    """
    Dependency provider for Flow Repository (singleton).

    Returns:
        FlowRepository: Configured flow repository instance (cached singleton)
    """
    return RepositoryFactory.create_flow_repository()


def get_flow_service(repository: FlowRepository = Depends(get_flow_repository)) -> FlowService:  # noqa: B008
    """Dependency provider for flow service.

    Args:
        repository: Injected repository instance

    Returns:
        FlowService: Service instance with injected repository
    """
    return FlowService(repository=repository)


@lru_cache(maxsize=1)
def get_job_management_service(flow_repository: FlowRepository = Depends(get_flow_repository)) -> JobManagementService:  # noqa: B008
    """
    Dependency provider for job management service (singleton).

    Returns:
        JobManagementService: Configured service instance (cached singleton)
    """
    factory = get_default_factory()
    return factory.create_job_management_service(flow_repository=flow_repository)

