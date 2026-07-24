"""
IncrementalMetadataFactory - Dependency injection and configuration.

This factory creates incremental metadata storage adapters based on configuration,
completely independent from job management storage configuration.

Configuration:
- Supports multiple storage backends (Filesystem, PostgreSQL)
- Environment-based configuration via YAML or environment variables
- Independent from job stats storage configuration
"""

import os
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from docpipe.core.constants import DocpipeConfigKeys, EnvironmentVariables
from docpipe.core.constants.constants import _find_project_root
from docpipe.core.incremental_metadata.adapters.stores import (
    FilesystemIncrementalMetadataStore,
    PostgresIncrementalMetadataStore,
)
from docpipe.core.incremental_metadata.domain import IncrementalMetadataStore
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class IncrementalStorageBackend(StrEnum):
    """Supported storage backends for incremental metadata."""

    FILESYSTEM = "filesystem"
    POSTGRESQL = "postgresql"


DEFAULT_CONFIG_PATH = _find_project_root() / "docling-pipelines-config.yaml"
ENV_CONFIG_PATH_KEY = EnvironmentVariables.DOCPIPE_CONFIG_PATH
ENV_INCREMENTAL_BASE_DIR_KEY = "DOCPIPE_INCREMENTAL_BASE_DIR"
ENV_INCREMENTAL_STORAGE_BACKEND_KEY = "DOCPIPE_INCREMENTAL_STORAGE_BACKEND"


class IncrementalMetadataFactory:
    """
    Factory for creating incremental metadata storage adapters.

    This factory handles:
    - Creating storage adapters based on configuration
    - Independent configuration from job management
    - Wiring dependencies between components
    - Providing singleton instances where appropriate

    Usage:
        # Create factory with configuration
        factory = IncrementalMetadataFactory(
            storage_backend=IncrementalStorageBackend.FILESYSTEM,
            config={"base_dir": "/path/to/data"}
        )

        # Get storage adapter
        store = factory.create_incremental_metadata_store()
    """

    def __init__(
        self,
        storage_backend: IncrementalStorageBackend = IncrementalStorageBackend.FILESYSTEM,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize factory with configuration.

        Args:
            storage_backend: Storage backend to use
            config: Optional configuration dictionary
        """
        self.storage_backend = storage_backend
        self.config = config or {}

        # Singleton instance
        self._store: IncrementalMetadataStore | None = None

        logger.info(f"IncrementalMetadataFactory initialized: storage={storage_backend}")

    def _resolve_base_dir(self) -> Path | None:
        """
        Resolve base directory from environment variable or configuration.

        Precedence:
        1. Environment variable (DOCPIPE_INCREMENTAL_BASE_DIR)
        2. Configuration (base_dir key)
        3. None (if neither is set)

        Returns:
            Resolved base directory path, or None if not configured.
            Creates the directory if it doesn't exist.
        """
        base_dir_override = os.getenv(ENV_INCREMENTAL_BASE_DIR_KEY)
        configured_base_dir = self.config.get(DocpipeConfigKeys.BASE_DIR)
        resolved_base_dir = None

        if base_dir_override:
            resolved_base_dir = Path(base_dir_override)
        elif configured_base_dir:
            configured_base_dir_path = Path(configured_base_dir)
            resolved_base_dir = (
                configured_base_dir_path
                if configured_base_dir_path.is_absolute()
                else configured_base_dir_path.resolve()
            )

        if resolved_base_dir:
            resolved_base_dir.mkdir(parents=True, exist_ok=True)

        return resolved_base_dir

    def create_incremental_metadata_store(self) -> IncrementalMetadataStore:
        """
        Create storage adapter based on configuration.

        Supports:
        - FILESYSTEM: Efficient columnar storage with PyArrow
        - POSTGRESQL: PostgreSQL database storage (production)

        Returns:
            IncrementalMetadataStore implementation
        """
        if self._store is not None:
            return self._store

        match self.storage_backend:
            case IncrementalStorageBackend.FILESYSTEM:
                resolved_base_dir = self._resolve_base_dir()
                lock_timeout = self.config.get(DocpipeConfigKeys.LOCK_TIMEOUT, 30.0)

                self._store = FilesystemIncrementalMetadataStore(
                    base_dir=resolved_base_dir,
                    lock_timeout=lock_timeout,
                    config=self.config,
                )
                logger.info(
                    f"Created FilesystemIncrementalMetadataStore: "
                    f"base_dir={resolved_base_dir}, "
                    f"lock_timeout={lock_timeout}s"
                )

            case IncrementalStorageBackend.POSTGRESQL:
                # Extract postgres config from nested structure if present
                postgres_config = self.config.get(DocpipeConfigKeys.POSTGRES, {})
                if postgres_config:
                    # Pass postgres config at top level for the store
                    store_config = {**postgres_config}
                    logger.debug(f"PostgreSQL config for incremental store: {store_config}")
                else:
                    store_config = self.config

                self._store = PostgresIncrementalMetadataStore(config=store_config)
                schema_name = store_config.get("schema", "incremental_metadata")
                logger.info(f"Created PostgresIncrementalMetadataStore with schema: {schema_name}")

            case _:
                raise ValueError(f"Unknown storage backend: {self.storage_backend}")

        assert self._store is not None, "Incremental metadata store must be initialized"
        return self._store

    @classmethod
    def from_config_file(cls, config_path: str) -> "IncrementalMetadataFactory":  # NOSONAR python:S3776
        """
        Create factory from YAML configuration file.

        If the config file doesn't exist, falls back to default values (Filesystem storage).

        Args:
            config_path: Path to YAML configuration file

        Returns:
            IncrementalMetadataFactory instance

        Raises:
            ValueError: If config is invalid
        """
        config_file = Path(config_path)

        if not config_file.exists():
            logger.warning(
                f"Configuration file not found: {config_path}. "
                f"Using default incremental metadata configuration (Filesystem storage)."
            )
            return cls()

        try:
            with open(config_file) as f:
                yaml_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}") from e

        if not yaml_config:
            logger.warning(f"Empty configuration file: {config_path}, using defaults")
            return cls()

        # Extract global_storage configuration (shared defaults)
        global_storage_config = yaml_config.get(DocpipeConfigKeys.GLOBAL_STORAGE, {})

        # Look for incremental_metadata section
        incremental_config = yaml_config.get(DocpipeConfigKeys.INCREMENTAL_METADATA, {})
        storage_config = incremental_config.get(DocpipeConfigKeys.INCREMENTAL_STORAGE, {}) or {}

        # Determine storage backend with precedence: service-specific > global_storage > defaults
        # First check service-specific config
        storage_str = storage_config.get(DocpipeConfigKeys.TYPE)
        # Fall back to global_storage if no service-specific config
        if not storage_str and global_storage_config:
            storage_str = global_storage_config.get(DocpipeConfigKeys.TYPE)
        # Final fallback to default
        if not storage_str:
            storage_str = IncrementalStorageBackend.FILESYSTEM.value

        try:
            storage_backend = IncrementalStorageBackend(storage_str)
        except ValueError:
            # Fail fast on invalid backend
            supported = [e.value for e in IncrementalStorageBackend]
            raise ValueError(
                f"Invalid storage backend '{storage_str}' for incremental metadata. Supported backends: {supported}"
            ) from None

        # Merge configuration with precedence: service-specific > global_storage > defaults
        merged_config: dict[str, Any] = {}

        # Start with global_storage config as base
        if global_storage_config:
            merged_config.update(global_storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})
            # Include postgres config from global_storage if present
            if DocpipeConfigKeys.POSTGRES in global_storage_config:
                merged_config[DocpipeConfigKeys.POSTGRES] = global_storage_config[DocpipeConfigKeys.POSTGRES]

        # Override with service-specific config
        merged_config.update(storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})

        # Include service-specific postgres config (overrides global if present)
        if DocpipeConfigKeys.POSTGRES in incremental_config:
            merged_config[DocpipeConfigKeys.POSTGRES] = incremental_config[DocpipeConfigKeys.POSTGRES]

        config_source = (
            "service-specific"
            if storage_config.get(DocpipeConfigKeys.TYPE)
            else ("global_storage" if global_storage_config else "defaults")
        )
        logger.info(
            f"Loaded incremental metadata configuration from {config_path}: "
            f"storage={storage_backend} (source: {config_source})"
        )

        return cls(storage_backend=storage_backend, config=merged_config)

    @classmethod
    def from_environment(cls) -> "IncrementalMetadataFactory":
        """
        Create factory from environment variables only.

        Environment variables:
        - DOCPIPE_INCREMENTAL_STORAGE_BACKEND: Storage backend (default: filesystem)
        - DOCPIPE_INCREMENTAL_BASE_DIR: Base directory for file-based storage

        Returns:
            IncrementalMetadataFactory instance
        """
        storage_raw = os.getenv(ENV_INCREMENTAL_STORAGE_BACKEND_KEY, IncrementalStorageBackend.FILESYSTEM.value)

        try:
            storage_backend = IncrementalStorageBackend(storage_raw)
        except ValueError:
            # Fail fast on invalid backend
            supported = [e.value for e in IncrementalStorageBackend]
            raise ValueError(
                f"Invalid storage backend '{storage_raw}' for incremental metadata. Supported backends: {supported}"
            ) from None

        logger.info(f"Creating incremental metadata factory from environment: storage={storage_backend}")

        return cls(storage_backend=storage_backend)

    @classmethod
    def from_default_sources(cls) -> "IncrementalMetadataFactory":
        """
        Create factory from default YAML config with environment overrides.

        Precedence:
        1. Environment variables for explicit overrides
        2. YAML config file (incremental_metadata section)
        3. Built-in defaults (Filesystem storage)
        """
        config_path = Path(os.getenv(ENV_CONFIG_PATH_KEY, str(DEFAULT_CONFIG_PATH)))

        if config_path.exists():
            try:
                factory = cls.from_config_file(str(config_path))
            except Exception as e:
                logger.warning(f"Failed to load incremental metadata config from {config_path}: {e}. Using defaults.")
                factory = cls()
        else:
            logger.warning(f"Config file not found at {config_path}. Using defaults for incremental metadata.")
            factory = cls()

        # Environment variable overrides
        storage_override = os.getenv(ENV_INCREMENTAL_STORAGE_BACKEND_KEY)
        if storage_override:
            try:
                factory.storage_backend = IncrementalStorageBackend(storage_override)
                logger.info(f"Overriding incremental metadata storage backend from environment: {storage_override}")
            except ValueError:
                logger.warning(
                    f"Invalid {ENV_INCREMENTAL_STORAGE_BACKEND_KEY} '{storage_override}', "
                    f"keeping {factory.storage_backend.value}"
                )

        logger.info(
            f"Created incremental metadata factory from default sources: "
            f"config_path={config_path}, storage={factory.storage_backend}"
        )
        return factory


# Singleton factory instance for convenience
_default_incremental_factory: IncrementalMetadataFactory | None = None


def get_default_incremental_factory() -> IncrementalMetadataFactory:
    """
    Get default incremental metadata factory instance (singleton).

    Returns:
        IncrementalMetadataFactory instance
    """
    global _default_incremental_factory

    if _default_incremental_factory is None:
        _default_incremental_factory = IncrementalMetadataFactory.from_default_sources()

    return _default_incremental_factory


def reset_default_incremental_factory() -> None:
    """
    Reset default incremental metadata factory instance (useful for testing).
    """
    global _default_incremental_factory
    _default_incremental_factory = None


def create_incremental_metadata_store(*, job_id: str | None = None) -> IncrementalMetadataStore:
    """
    Create incremental metadata store from docling-pipelines-config.yaml.

    This is the primary entry point for creating incremental metadata stores.
    Configuration is loaded from the docling-pipelines-config.yaml file's
    incremental_metadata section.

    The store is job-agnostic and can be used across multiple jobs.
    Job IDs are passed to individual store methods, not at creation time.

    Args:
        job_id: Optional job identifier for logging purposes only

    Returns:
        Configured incremental metadata store

    Raises:
        ValueError: If configuration is invalid or missing
        FileNotFoundError: If required configuration file is not found

    Example YAML configuration:
        incremental_metadata:
          storage:
            type: "filesystem"  # Options: filesystem, postgresql
            config:
              base_dir: "/path/to/metadata"
              lock_timeout: 30.0

          # PostgreSQL config (when type is "postgresql")
          postgres:
            host: "localhost"
            port: 5432
            database: "docpipe"
            user: "docpipe_user"
            password: "${POSTGRES_PASSWORD}"
            schema: "incremental_metadata"
    """
    factory = get_default_incremental_factory()
    store = factory.create_incremental_metadata_store()

    if job_id:
        logger.info(f"Created incremental metadata store for job_id={job_id} using {factory.storage_backend} backend")
    else:
        logger.info(f"Created incremental metadata store using {factory.storage_backend} backend")

    return store
