"""Factory for creating repository instances for all asset types.

Provides centralized repository creation based on environment configuration.
Supports multiple repository types through the Abstract Factory pattern with
registry-based extensibility.

This factory bridges the gap between configuration-based repository selection
(from docling-pipelines-config.yaml) and the unified asset architecture's
dependency injection pattern.

Architecture:
    - AbstractRepositoryType: Base enum for all repository types
    - RepositoryType: Concrete repository types (LOCAL)
    - get_available_repository_types(): Registry mapping types to implementation classes
    - create_repository(): Generic factory method using registry pattern


"""

import logging
import os
from enum import Enum
from pathlib import Path
from typing import TypeVar

import yaml

from docpipe.core.assets.common.adapters.repositories.local_asset_repository import LocalAssetRepository
from docpipe.core.assets.common.domain.models.asset import Asset
from docpipe.core.assets.common.domain.ports.asset_repository import AssetRepository
from docpipe.exceptions.docpipe_exceptions import RepositoryConfigurationException

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Asset)


class AbstractRepositoryType(Enum):
    """Base enumeration for repository types.

    Empty base class that allows different implementations to define their own
    repository types without conflicts. Can be extended to add custom repository
    types in derived implementations.
    """

    pass


class RepositoryType(AbstractRepositoryType):
    """Enumeration of available repository types in OSS."""

    LOCAL = "local"


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[5] / "docling-pipelines-config.yaml"
ENV_CONFIG_PATH_KEY = "DOCPIPE_CONFIG_PATH"


class RepositoryFactory:
    """Factory for creating AssetRepository instances for any asset type.

    Enables switching between repository implementations via environment
    configuration. Follows the Abstract Factory pattern for extensibility.

    Configuration precedence:
        1. Environment variables
        2. docling-pipelines-config.yaml
        3. Built-in defaults

    YAML Configuration (docling-pipelines-config.yaml):
        assets_management:
          flow_repository:
            type: local
            config:
              base_dir: sample_flows

    Environment Variables:
        FLOW_REPOSITORY_TYPE: Repository type for flows (default: "local")
        FLOW_REPOSITORY_BASE_DIR: Directory for local flow storage
    """

    @classmethod
    def get_available_repository_types(cls) -> dict[AbstractRepositoryType, type]:
        """Get available repository types and their implementation classes.

        Returns a mapping of repository type enums to their corresponding
        AssetRepository implementation classes. This enables dynamic repository
        instantiation and allows extended implementations to add additional
        repository types by overriding this method.

        Note:
            This is a classmethod (not staticmethod) to support inheritance.
            When a subclass overrides this method, other methods in the class
            will automatically use the subclass's version via the cls parameter.

        Returns:
            Dictionary mapping AbstractRepositoryType to repository class

        Example:
            {
                RepositoryType.LOCAL: LocalAssetRepository
            }
        """
        return {RepositoryType.LOCAL: LocalAssetRepository}

    @classmethod
    def _get_valid_types(cls) -> list[str]:
        """Get list of valid repository type values.

        Note:
            Uses cls.get_available_repository_types() instead of
            RepositoryFactory.get_available_repository_types() to ensure
            subclass overrides are respected.

        Returns:
            List of valid repository type strings from available repository types
        """
        available_types = cls.get_available_repository_types()
        return [repo_type.value for repo_type in available_types.keys()]

    @staticmethod
    def _load_yaml_config() -> dict:
        """Load configuration from YAML file.

        Returns:
            Dictionary containing YAML configuration, or empty dict if file not found
        """
        config_path = Path(os.getenv(ENV_CONFIG_PATH_KEY, str(DEFAULT_CONFIG_PATH)))
        if not config_path.exists():
            return {}

        try:
            with open(config_path) as file:
                yaml_config = yaml.safe_load(file)
        except yaml.YAMLError as exc:
            logger.warning(f"Invalid repository YAML configuration at {config_path}: {exc}")
            return {}

        return yaml_config or {}

    @staticmethod
    def _get_repository_config(*, asset_type_name: str) -> tuple[str, dict]:
        """Get repository configuration from environment and YAML for a specific asset type.

        Args:
            asset_type_name: Name of asset type (e.g., "flow", "document_set")

        Returns:
            Tuple of (repository_type_string, config_dict)
        """
        yaml_config = RepositoryFactory._load_yaml_config()
        assets_config = yaml_config.get("assets_management", {}) or {}
        repo_config = assets_config.get(f"{asset_type_name}_repository", {}) or {}

        # Environment variable pattern: FLOW_REPOSITORY_TYPE, DOCUMENT_SET_REPOSITORY_TYPE, etc.
        env_type_key = f"{asset_type_name.upper()}_REPOSITORY_TYPE"
        env_base_dir_key = f"{asset_type_name.upper()}_REPOSITORY_BASE_DIR"

        repo_type_str = os.getenv(env_type_key, repo_config.get("type", RepositoryType.LOCAL.value))
        resolved_config = repo_config.get("config", {}) or {}

        # Allow environment variable to override base_dir
        if env_base_dir_key in os.environ:
            resolved_config["base_dir"] = os.environ[env_base_dir_key]

        return repo_type_str, resolved_config

    @classmethod
    def create_repository(cls, *, asset_type: type[T]) -> AssetRepository[T]:
        """Create a repository for the specified asset type based on configuration.

        Uses a registry pattern to dynamically instantiate repository implementations.
        This allows extended implementations to add additional repository types
        without modifying existing code.

        Args:
            asset_type: The asset type class (Flow, DocumentSet, DocumentLibrary, etc.)

        Note:
            This is a classmethod to support inheritance. When called on a subclass,
            it will use the subclass's get_available_repository_types() registry.

        Returns:
            AssetRepository[T]: Configured repository instance for the asset type

        Raises:
            RepositoryConfigurationException: If repository type is invalid
                                             or not yet implemented

        Example:
            from docpipe.core.assets.flows.domain.models.flow import Flow
            flow_repo = RepositoryFactory.create_repository(asset_type=Flow)
        """
        # Get asset type name for config lookup (e.g., "flow" from Flow class)
        asset_type_name = asset_type.__name__.lower()

        repo_type_str, repository_config = cls._get_repository_config(asset_type_name=asset_type_name)
        available_types = cls.get_available_repository_types()
        valid_types = cls._get_valid_types()

        logger.info(f"Creating {asset_type_name} repository of type: '{repo_type_str}'")

        if repo_type_str.lower() not in valid_types:
            logger.error(
                f"Invalid repository type: '{repo_type_str}'. Must be one of: {', '.join(valid_types)}",
            )
            raise RepositoryConfigurationException(
                f"Invalid repository type: '{repo_type_str}'. Must be one of: {', '.join(valid_types)}",
                repository_type=repo_type_str,
                valid_types=valid_types,
            )

        # Find matching repository type enum from registry
        repository_type = None
        for repo_enum in available_types.keys():
            if repo_enum.value == repo_type_str.lower():
                repository_type = repo_enum
                break

        if not repository_type:
            raise RepositoryConfigurationException(
                f"Repository type '{repo_type_str}' not found in registry",
                repository_type=repo_type_str,
                valid_types=valid_types,
            )

        # Get repository class from registry and instantiate
        repository_class = available_types[repository_type]

        try:
            if repository_type == RepositoryType.LOCAL:
                # For LocalAssetRepository, pass asset_type and storage_path
                # Default storage path based on asset type
                default_base_dir = {
                    "flow": "sample_flows",
                    "documentset": "document_sets",
                    "documentlibrary": "document_libraries",
                }.get(asset_type_name, "assets")

                storage_path = repository_config.get("base_dir", default_base_dir)
                # LocalAssetRepository requires asset_type and storage_path as keyword args
                return repository_class(asset_type=asset_type, storage_path=storage_path)

            # For other repository types (CAMS, etc.), pass all configuration
            # Enterprise implementations will define their own constructor signatures
            return repository_class(asset_type=asset_type, **repository_config)
        except TypeError as e:
            raise RepositoryConfigurationException(
                f"Failed to instantiate repository '{repository_type.value}' for {asset_type_name}: {e}",
                repository_type=repository_type.value,
                valid_types=valid_types,
            ) from e
