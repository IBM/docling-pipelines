"""Factory for creating incremental metadata store adapters with decorator-based registration.

This factory enables automatic registration of incremental metadata store adapters
through decorators, following the same pattern as OperatorSourceFactory.
"""

import os
import threading
from pathlib import Path
from typing import Any, ClassVar

import yaml

from docpipe.core.constants import DocpipeConfigKeys, EnvironmentVariables
from docpipe.core.constants.constants import _find_project_root
from docpipe.core.incremental_metadata.domain import IncrementalMetadataStore
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


DEFAULT_STORAGE_BACKEND = "filesystem"

DEFAULT_CONFIG_PATH = _find_project_root() / "docling-pipelines-config.yaml"
ENV_CONFIG_PATH_KEY = EnvironmentVariables.DOCPIPE_CONFIG_PATH
ENV_INCREMENTAL_BASE_DIR_KEY = "DOCPIPE_INCREMENTAL_BASE_DIR"


class IncrementalMetadataFactory:
    """Factory for creating incremental metadata store adapters.

    This factory maintains a registry of available store adapters and
    provides methods to create instances based on backend names.

    Usage:
        # Register a store
        @register_incremental_update_store
        class FilesystemIncrementalMetadataStore(IncrementalMetadataStore):
            STORE_BACKEND = "filesystem"
            ...

        # Create a store instance
        store = IncrementalMetadataFactory.create("filesystem", config={...})
    """

    _stores: ClassVar[dict[str, type[IncrementalMetadataStore]]] = {}

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered backends. Intended for test teardown only."""
        cls._stores.clear()

    @classmethod
    def register(cls, store_class: type[IncrementalMetadataStore]) -> type[IncrementalMetadataStore]:
        """Register an incremental metadata store class.

        Args:
            store_class: The store class to register. Must define STORE_BACKEND.

        Returns:
            The store class (for decorator chaining).

        Raises:
            TypeError: If store_class doesn't define STORE_BACKEND.
        """
        if not hasattr(store_class, "STORE_BACKEND"):
            raise TypeError(f"Store class {store_class.__name__} must define STORE_BACKEND")

        backend_name: str = store_class.STORE_BACKEND  # type: ignore[attr-defined]

        if backend_name in cls._stores:
            logger.warning("Store backend '%s' is already registered. Overwriting.", backend_name)

        cls._stores[backend_name] = store_class
        logger.debug("Registered incremental metadata store: %s", backend_name)

        return store_class

    @classmethod
    def create(cls, backend_name: str, *, config: dict[str, Any] | None = None) -> IncrementalMetadataStore:
        """Create an incremental metadata store instance.

        Args:
            backend_name: Name of the backend to create (must match a registered STORE_BACKEND).
            config: Configuration dictionary passed to the store constructor.

        Returns:
            Initialized store instance.

        Raises:
            ValueError: If backend_name is not registered.
        """
        if backend_name not in cls._stores:
            available = ", ".join(cls._stores.keys()) if cls._stores else "none"
            raise DocpipeException(
                f"Unknown incremental metadata store backend: '{backend_name}'. Available backends: {available}"
            )

        store_class = cls._stores[backend_name]
        logger.debug("Creating incremental metadata store: %s", backend_name)
        return store_class(config=config or {})  # type: ignore[call-arg]

    @classmethod
    def list_backends(cls) -> list[str]:
        """List all registered backend names.

        Returns:
            List of registered backend names.
        """
        return list(cls._stores.keys())


def register_incremental_update_store(
    store_class: type[IncrementalMetadataStore],
) -> type[IncrementalMetadataStore]:
    """Decorator to register an incremental metadata store class.

    The decorated class must define a STORE_BACKEND class attribute whose value
    is the string used in YAML config / environment variable to select this store
    (e.g. "filesystem", "postgresql").

    Usage:
        @register_incremental_update_store
        class FilesystemIncrementalMetadataStore(IncrementalMetadataStore):
            STORE_BACKEND = "filesystem"
            ...

    Args:
        store_class: The store class to register.

    Returns:
        The store class unchanged (for decorator chaining).
    """
    return IncrementalMetadataFactory.register(store_class)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _resolve_backend_and_config(*, yaml_config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract backend name and merged config dict from a parsed YAML document."""
    global_storage_config = yaml_config.get(DocpipeConfigKeys.GLOBAL_STORAGE, {})
    incremental_config = yaml_config.get(DocpipeConfigKeys.INCREMENTAL_METADATA, {})
    storage_config = incremental_config.get(DocpipeConfigKeys.INCREMENTAL_STORAGE, {}) or {}

    # Precedence: service-specific > global_storage > default
    backend = (
        storage_config.get(DocpipeConfigKeys.TYPE)
        or global_storage_config.get(DocpipeConfigKeys.TYPE)
        or DEFAULT_STORAGE_BACKEND
    )

    if backend not in IncrementalMetadataFactory._stores:
        available = ", ".join(IncrementalMetadataFactory._stores.keys()) or "none"
        raise DocpipeException(
            f"Invalid storage backend '{backend}' for incremental metadata. Available backends: {available}"
        )

    # Merge config: global_storage base, overridden by service-specific
    # Mirrors the same pattern in job_management_factory.py so both stores
    # accept the same global_storage.postgres YAML block.
    merged: dict[str, Any] = {}
    if global_storage_config:
        merged.update(global_storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})
        if DocpipeConfigKeys.POSTGRES in global_storage_config:
            merged[DocpipeConfigKeys.POSTGRES] = global_storage_config[DocpipeConfigKeys.POSTGRES]
    merged.update(storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})
    if DocpipeConfigKeys.POSTGRES in incremental_config:
        merged[DocpipeConfigKeys.POSTGRES] = incremental_config[DocpipeConfigKeys.POSTGRES]

    return backend, merged


def create_store_from_config_file(*, config_path: str) -> IncrementalMetadataStore:
    """Create an incremental metadata store from a YAML configuration file.

    Falls back to the default filesystem store if the file does not exist or is empty.

    Args:
        config_path: Path to YAML configuration file.

    Returns:
        Configured IncrementalMetadataStore instance.

    Raises:
        ValueError: If the YAML is malformed or the backend is not registered.
    """
    config_file = Path(config_path)

    if not config_file.exists():
        logger.warning(
            "Configuration file not found: %s. Using default incremental metadata configuration.",
            config_path,
        )
        return _create_default_store()

    try:
        with open(config_file) as f:
            yaml_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise DocpipeException(f"Invalid YAML configuration: {e}") from e

    if not yaml_config:
        logger.warning("Empty configuration file: %s, using defaults", config_path)
        return _create_default_store()

    backend, config = _resolve_backend_and_config(yaml_config=yaml_config)
    logger.info("Creating incremental metadata store from %s: backend=%s", config_path, backend)
    return IncrementalMetadataFactory.create(backend, config=config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_default_store() -> IncrementalMetadataStore:
    """Create the default store, raising a clear error if it is not registered."""
    if DEFAULT_STORAGE_BACKEND not in IncrementalMetadataFactory._stores:
        available = ", ".join(IncrementalMetadataFactory._stores.keys()) or "none"
        raise RuntimeError(
            f"Default storage backend '{DEFAULT_STORAGE_BACKEND}' is not registered. "
            f"Ensure the filesystem store module is imported before calling this function. "
            f"Available backends: {available}"
        )
    return IncrementalMetadataFactory.create(DEFAULT_STORAGE_BACKEND)


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------

_default_store: IncrementalMetadataStore | None = None
_default_store_lock: threading.Lock = threading.Lock()


def create_incremental_metadata_store(*, job_id: str | None = None) -> IncrementalMetadataStore:
    """Create (or return the cached) incremental metadata store.

    Configuration is loaded from docling-pipelines-config.yaml
    (incremental_metadata section).

    The store is job-agnostic; job IDs are passed to individual store methods.

    Args:
        job_id: Optional job identifier for logging purposes only.

    Returns:
        Configured IncrementalMetadataStore instance.

    Example YAML configuration:
        incremental_metadata:
          storage:
            type: "filesystem"   # any registered STORE_BACKEND value
            config:
              base_dir: "/path/to/metadata"
              lock_timeout: 30.0
    """
    global _default_store

    if _default_store is None:
        with _default_store_lock:
            # Double-checked locking: re-check inside the lock
            if _default_store is None:
                config_path = Path(os.getenv(ENV_CONFIG_PATH_KEY, str(DEFAULT_CONFIG_PATH)))

                if config_path.exists():
                    try:
                        _default_store = create_store_from_config_file(config_path=str(config_path))
                    except Exception as e:
                        logger.warning("Failed to load config from %s: %s. Using defaults.", config_path, e)
                        _default_store = _create_default_store()
                else:
                    logger.warning("Config file not found at %s. Using defaults.", config_path)
                    _default_store = _create_default_store()

    if job_id:
        logger.info("Returning incremental metadata store for job_id=%s", job_id)

    assert _default_store is not None, "Incremental metadata store was not initialised"
    return _default_store


def reset_default_incremental_store() -> None:
    """Reset the cached store (useful for testing)."""
    global _default_store
    with _default_store_lock:
        _default_store = None
