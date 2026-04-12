"""Factory for creating repository instances.

Provides centralized repository creation based on environment configuration.
Supports multiple repository types through the Abstract Factory pattern.
"""

import logging
import os
from enum import Enum

from common.exceptions.datasift_exceptions import RepositoryConfigurationException
from core.assets_management.adapters.repositories.local.local_flow_repository import LocalFlowRepository
from core.assets_management.domain.ports.flow_repository import FlowRepository

logger = logging.getLogger(__name__)


class RepositoryType(Enum):
    """Enumeration of available repository types."""

    LOCAL = "local"


class RepositoryFactory:
    """Factory for creating FlowRepository instances.

    Enables switching between repository implementations via environment
    configuration. Follows the Abstract Factory pattern for extensibility.

    Environment Variables:
        FLOW_REPOSITORY_TYPE: Repository type (default: "local")
                             Valid values: "local"
        LOCAL_FLOWS_DIR: Directory for local repository storage
                        (default: ~/Documents/pipeline/assets)
                        Only used when FLOW_REPOSITORY_TYPE="local"
    """

    @staticmethod
    def _get_valid_types() -> list[str]:
        """Get list of valid repository type values.

        Returns:
            List of valid repository type strings from RepositoryType enum
        """
        return [t.value for t in RepositoryType]

    @staticmethod
    def create_flow_repository() -> FlowRepository:
        """Create a flow repository based on environment configuration.

        Reads FLOW_REPOSITORY_TYPE to determine repository implementation.
        Each repository type reads its own specific configuration from
        environment variables (e.g., LOCAL_FLOWS_DIR for local type).

        Returns:
            FlowRepository: Configured repository instance

        Raises:
            RepositoryConfigurationException: If repository type is invalid
                                             or not yet implemented

        Note:
            Currently only "local" type is implemented. Future types may
            include "git", "s3", "database", etc.
        """
        repo_type_str = os.getenv("FLOW_REPOSITORY_TYPE", "local")
        valid_types = RepositoryFactory._get_valid_types()

        logger.info(
            f"Creating flow repository of type: '{repo_type_str}'",
        )

        if repo_type_str.lower() not in valid_types:
            logger.info(
                f"Invalid repository type: '{repo_type_str}'. Must be one of: {', '.join(valid_types)}",
            )
            raise RepositoryConfigurationException(
                f"Invalid repository type: '{repo_type_str}'. Must be one of: {', '.join(valid_types)}",
                repository_type=repo_type_str,
                valid_types=valid_types,
            )

        repository_type = RepositoryType(repo_type_str.lower())

        match repository_type:
            case RepositoryType.LOCAL:
                return LocalFlowRepository()
            case _:
                raise RepositoryConfigurationException(
                    f"Repository type '{repository_type.value}' is not yet implemented",
                    repository_type=repository_type.value,
                    valid_types=valid_types,
                )

    @staticmethod
    def create_default_flow_repository() -> FlowRepository:
        """Create a FlowRepository with default configuration.

        Convenience method that creates LocalFlowRepository with default settings.
        Equivalent to calling create_flow_repository() with FLOW_REPOSITORY_TYPE="local".

        Returns:
            FlowRepository: LocalFlowRepository instance with default configuration
        """
        logger.info("Creating default FlowRepository (LocalFlowRepository)")
        return LocalFlowRepository()
