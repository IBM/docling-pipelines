"""Incremental metadata factory — adapter registry and DI container.

Mirrors ``JobManagementFactory``:
- Class-level registry of ``IncrementalMetadataStore`` adapters.
- Instance-level lazy singletons for the store and ``IncrementalUpdateService``.
- Module-level ``get_default_factory()`` for the process-wide singleton factory instance.
- ``get_incremental_update_service()`` convenience function for callers that
  only need the service.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import yaml

from docpipe.core.constants import DocpipeConfigKeys, EnvironmentVariables
from docpipe.core.constants.constants import _find_project_root
from docpipe.core.incremental_metadata.domain import IncrementalMetadataStore
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from docpipe.core.incremental_metadata.application.services import IncrementalUpdateService

logger = get_logger(__name__)

DEFAULT_STORAGE_BACKEND = "filesystem"
DEFAULT_CONFIG_PATH = _find_project_root() / "docling-pipelines-config.yaml"
ENV_CONFIG_PATH_KEY = EnvironmentVariables.DOCPIPE_CONFIG_PATH
ENV_INCREMENTAL_BASE_DIR_KEY = "DOCPIPE_INCREMENTAL_BASE_DIR"


class IncrementalMetadataFactory:
    """Adapter registry and DI container for incremental metadata.

    Class-level registry
    --------------------
    Store adapters are registered via ``@register_incremental_update_store``.

    Instance-level DI container
    ---------------------------
    Each factory instance lazily owns one store and one service.  Use
    ``get_default_factory()`` to get the process-wide singleton factory, then
    call ``get_store()`` or ``get_service()`` on it.

    Example::

        service = get_incremental_update_service()   # simplest call
        store   = get_default_factory().get_store()  # if you only need the store
    """

    # ------------------------------------------------------------------ #
    # Class-level adapter registry                                         #
    # ------------------------------------------------------------------ #

    _stores: ClassVar[dict[str, type[IncrementalMetadataStore]]] = {}

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered backends.  Intended for test teardown only."""
        cls._stores.clear()

    @classmethod
    def register(cls, store_class: type[IncrementalMetadataStore]) -> type[IncrementalMetadataStore]:
        """Register an incremental metadata store class.

        Args:
            store_class: Must define a ``STORE_BACKEND`` class attribute.

        Returns:
            The store class unchanged (supports decorator chaining).

        Raises:
            TypeError: If ``STORE_BACKEND`` is missing.
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
    def list_backends(cls) -> list[str]:
        """Return all registered backend names."""
        return list(cls._stores.keys())

    # ------------------------------------------------------------------ #
    # Instance — DI container                                              #
    # ------------------------------------------------------------------ #

    def __init__(self, *, backend: str, config: dict[str, Any] | None = None) -> None:
        """
        Args:
            backend: Registered ``STORE_BACKEND`` value (e.g. ``"filesystem"``).
            config:  Configuration dict forwarded to the store constructor.
        """
        self._backend = backend
        self._config: dict[str, Any] = config or {}
        self._store: IncrementalMetadataStore | None = None
        self._service: IncrementalUpdateService | None = None

    def get_store(self) -> IncrementalMetadataStore:
        """Return the singleton store, creating it on first call."""
        if self._store is None:
            if self._backend not in IncrementalMetadataFactory._stores:
                available = ", ".join(IncrementalMetadataFactory._stores.keys()) or "none"
                raise DocpipeException(
                    f"Unknown incremental metadata store backend: '{self._backend}'. Available backends: {available}"
                )
            store_class = IncrementalMetadataFactory._stores[self._backend]
            self._store = store_class(config=self._config)  # type: ignore[call-arg]
            logger.info("Created IncrementalMetadataStore: backend=%s", self._backend)
        return self._store

    def get_service(self) -> IncrementalUpdateService:
        """Return the singleton ``IncrementalUpdateService``, creating it on first call."""
        if self._service is None:
            # Deferred import to avoid circular dependency at module load time.
            from docpipe.core.incremental_metadata.application.services import (
                IncrementalUpdateService,
            )

            self._service = IncrementalUpdateService(store=self.get_store())
            logger.info("Created IncrementalUpdateService")
        return self._service

    # ------------------------------------------------------------------ #
    # Named constructors                                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_config_file(cls, *, config_path: str) -> IncrementalMetadataFactory:
        """Build a factory from a YAML configuration file.

        Falls back to the default filesystem backend when the file is absent or
        empty.

        Args:
            config_path: Path to ``docling-pipelines-config.yaml``.

        Returns:
            Configured ``IncrementalMetadataFactory`` instance.

        Raises:
            DocpipeException: If the YAML is malformed or the resolved backend
                is not registered.
        """
        config_file = Path(config_path)

        if not config_file.exists():
            logger.warning(
                "Configuration file not found: %s. Using default incremental metadata configuration.",
                config_path,
            )
            return cls._default_backend_factory()

        try:
            with Path(config_file).open() as f:
                yaml_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise DocpipeException(f"Invalid YAML configuration: {e}") from e

        if not yaml_config:
            logger.warning("Empty configuration file: %s. Using defaults.", config_path)
            return cls._default_backend_factory()

        backend, config = _resolve_backend_and_config(yaml_config=yaml_config)
        logger.info("Incremental metadata factory from %s: backend=%s", config_path, backend)
        return cls(backend=backend, config=config)

    @classmethod
    def from_default_sources(cls) -> IncrementalMetadataFactory:
        """Build a factory from the standard config-file / env-var path.

        Resolution order:
        1. ``DOCPIPE_CONFIG_PATH`` environment variable
        2. ``<project_root>/docling-pipelines-config.yaml``
        3. Filesystem default (when no config file is found)
        """
        config_path = Path(os.getenv(ENV_CONFIG_PATH_KEY, str(DEFAULT_CONFIG_PATH)))
        if config_path.exists():
            try:
                return cls.from_config_file(config_path=str(config_path))
            except Exception as e:
                logger.warning("Failed to load config from %s: %s. Using defaults.", config_path, e)
        else:
            logger.warning("Config file not found at %s. Using defaults.", config_path)
        return cls._default_backend_factory()

    @classmethod
    def _default_backend_factory(cls) -> IncrementalMetadataFactory:
        if DEFAULT_STORAGE_BACKEND not in cls._stores:
            available = ", ".join(cls._stores.keys()) or "none"
            raise RuntimeError(
                f"Default storage backend '{DEFAULT_STORAGE_BACKEND}' is not registered. "
                f"Ensure the filesystem store module is imported before calling this. "
                f"Available backends: {available}"
            )
        return cls(backend=DEFAULT_STORAGE_BACKEND)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def register_incremental_update_store(
    store_class: type[IncrementalMetadataStore],
) -> type[IncrementalMetadataStore]:
    """Register an incremental metadata store class via decorator.

    The decorated class must define a ``STORE_BACKEND`` class attribute whose
    value is the string used in YAML config to select this store
    (e.g. ``"filesystem"``, ``"postgresql"``).

    Usage::

        @register_incremental_update_store
        class FilesystemIncrementalMetadataStore(IncrementalMetadataStore):
            STORE_BACKEND = "filesystem"
    """
    return IncrementalMetadataFactory.register(store_class)


# ---------------------------------------------------------------------------
# Internal config helper
# ---------------------------------------------------------------------------


def _resolve_backend_and_config(*, yaml_config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract backend name and merged config dict from a parsed YAML document."""
    global_storage_config = yaml_config.get(DocpipeConfigKeys.GLOBAL_STORAGE, {})
    incremental_config = yaml_config.get(DocpipeConfigKeys.INCREMENTAL_METADATA, {})
    storage_config: Any | dict[Any, Any] = incremental_config.get(DocpipeConfigKeys.STORAGE, {}) or {}

    # Precedence: service-specific > global_storage > default
    backend = (
        storage_config.get(DocpipeConfigKeys.TYPE)
        or global_storage_config.get(DocpipeConfigKeys.TYPE)
        or DEFAULT_STORAGE_BACKEND
    )

    if backend not in IncrementalMetadataFactory._stores:
        available = ", ".join(IncrementalMetadataFactory._stores.keys()) or "none"
        raise DocpipeException(f"Invalid storage backend '{backend}' for incremental metadata. Available: {available}")

    # Merge config: global_storage base, overridden by service-specific block.
    merged: dict[str, Any] = {}
    if global_storage_config:
        merged.update(global_storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})
        if DocpipeConfigKeys.POSTGRES in global_storage_config:
            merged[DocpipeConfigKeys.POSTGRES] = global_storage_config[DocpipeConfigKeys.POSTGRES]
    merged.update(storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})
    if DocpipeConfigKeys.POSTGRES in incremental_config:
        merged[DocpipeConfigKeys.POSTGRES] = incremental_config[DocpipeConfigKeys.POSTGRES]

    return backend, merged


# ---------------------------------------------------------------------------
# Module-level singleton factory  (mirrors get_default_factory in job_management)
# ---------------------------------------------------------------------------

_default_factory: IncrementalMetadataFactory | None = None
_default_factory_lock: threading.Lock = threading.Lock()


def get_default_factory() -> IncrementalMetadataFactory:
    """Return the process-wide singleton ``IncrementalMetadataFactory``.

    Built once from standard config-file / env-var sources on first call.
    The store and service it owns are also lazy singletons on the factory.
    """
    global _default_factory

    if _default_factory is None:
        with _default_factory_lock:
            if _default_factory is None:
                _default_factory = IncrementalMetadataFactory.from_default_sources()

    return _default_factory


def set_default_factory(factory: IncrementalMetadataFactory) -> None:
    """Replace the process-wide singleton factory.

    Intended for callers that need to install a pre-configured factory
    before any component requests the singleton.  Thread-safe: acquires
    the same lock used by get_default_factory().

    Args:
        factory: The IncrementalMetadataFactory instance to install as
                 the process-wide singleton.
    """
    global _default_factory
    with _default_factory_lock:
        _default_factory = factory


def get_incremental_update_service() -> IncrementalUpdateService:
    """Return the process-wide singleton ``IncrementalUpdateService``.

    Thin convenience wrapper over ``get_default_factory().get_service()``.
    All callers share the same store and service instance.
    """
    return get_default_factory().get_service()
