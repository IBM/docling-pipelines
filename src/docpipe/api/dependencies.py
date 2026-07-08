"""
Application-level dependency providers for FastAPI.

This module provides dependency injection for job management services
and other application-level components.
"""

from functools import lru_cache

from fastapi import Depends

from docpipe.core.assets.common.domain.ports.asset_repository import AssetRepository
from docpipe.core.assets.common.factories.repository_factory import RepositoryFactory
from docpipe.core.assets.flows.application.services import FlowService
from docpipe.core.assets.flows.domain.models.flow import Flow
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
def get_flow_repository() -> AssetRepository[Flow]:
    """
    Dependency provider for Flow Repository (singleton).

    Uses RepositoryFactory to create repository based on configuration from
    docling-pipelines-config.yaml. This enables:
    - OSS: LocalAssetRepository[Flow] (filesystem-based)

    Returns:
        AssetRepository[Flow]: Configured flow repository instance (cached singleton)
    """
    return RepositoryFactory.create_repository(asset_type=Flow)


def get_flow_service(repository: AssetRepository[Flow] = Depends(get_flow_repository)) -> FlowService:  # noqa: B008
    """Dependency provider for flow service.

    Args:
        repository: Injected repository instance

    Returns:
        FlowService: Service instance with injected repository
    """
    return FlowService(repository=repository)


@lru_cache(maxsize=1)
def get_job_management_service(flow_service: FlowService = Depends(get_flow_service)) -> JobManagementService:  # noqa: B008
    """
    Dependency provider for job management service (singleton).

    Returns:
        JobManagementService: Configured service instance (cached singleton)
    """
    factory = get_default_factory()
    return factory.create_job_management_service(flow_service=flow_service)
