"""Flow definition snapshot storage factory — adapter registry.

- Class-level registry of ``KeyValueStoragePort`` adapters.
- Instance-level lazy singletons for the store.
- Module-level ``get_default_factory()`` for the process-wide singleton factory instance.
- ``get_flow_definitions_snapshot_storage()`` convenience function for callers that
  need the storage adopter.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import yaml

from docpipe.core.constants import DocpipeConfigKeys, EnvironmentVariables
from docpipe.core.constants.constants import _find_project_root
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure import get_data_path
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)

DEFAULT_STORAGE_BACKEND = "filesystem"
DEFAULT_CONFIG_PATH = _find_project_root() / "docling-pipelines-config.yaml"
ENV_CONFIG_PATH_KEY = EnvironmentVariables.DOCPIPE_CONFIG_PATH

if TYPE_CHECKING:
    from docpipe.storage import KeyValueStoragePort


class FlowDefinitionSnapshotStorageFactory:
    """Adapter registry for Flow definition snapshot storage.

    Class-level registry
    --------------------
    Store adapters are registered via ``@register_flow_definition_snapshot_storage``.

    Instance-level DI container
    ---------------------------
    Each factory instance lazily owns one storage.  Use
    ``get_default_factory()`` to get the process-wide singleton factory, then
    call ``get_store()`` on it.

    Example::
        store = get_flow_definitions_snapshot_storage()
    """

    # ------------------------------------------------------------------ #
    # Class-level adapter registry                                         #
    # ------------------------------------------------------------------ #

    _stores: ClassVar[dict[str, type[KeyValueStoragePort]]] = {}

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered backends.  Intended for test teardown only."""
        cls._stores.clear()

    @classmethod
    def register(cls, store_class: type[KeyValueStoragePort]) -> type[KeyValueStoragePort]:
        """Register a flow definition snapshot storage class.

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
        self._store: KeyValueStoragePort | None = None

    def get_store(self) -> KeyValueStoragePort:
        """Return the singleton store, creating it on first call."""
        if self._store is None:
            if self._backend not in FlowDefinitionSnapshotStorageFactory._stores:
                available = ", ".join(FlowDefinitionSnapshotStorageFactory._stores.keys()) or "none"
                raise DocpipeException(
                    f"Unknown flow Definition snapshot store backend: '{self._backend}'. Available backends: {available}"
                )
            store_class = FlowDefinitionSnapshotStorageFactory._stores[self._backend]
            base_dir = self._config.get(DocpipeConfigKeys.BASE_DIR) or get_data_path()
            self._store = store_class(base_dir=base_dir)  # type: ignore[call-arg]
            logger.info("Created flow definition snapshot store: backend=%s", self._backend)
        return self._store

    @classmethod
    def from_config_file(cls, *, config_path: str) -> FlowDefinitionSnapshotStorageFactory:
        """Build a factory from a YAML configuration file.

        Falls back to the default filesystem backend when the file is absent or
        empty.

        Args:
            config_path: Path to ``docling-pipelines-config.yaml``.

        Returns:
            Configured ``FlowDefinitionSnapshotStorageFactory`` instance.

        Raises:
            DocpipeException: If the YAML is malformed or the resolved backend is not registered.
        """
        config_file = Path(config_path)

        if not config_file.exists():
            logger.warning(
                "Configuration file not found: %s. Using default flow_definition_snapshot configuration.",
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
        logger.info("Flow definition snapshot storage factory from %s: backend=%s", config_path, backend)
        return cls(backend=backend, config=config)

    @classmethod
    def from_default_sources(cls) -> FlowDefinitionSnapshotStorageFactory:
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
    def _default_backend_factory(cls) -> FlowDefinitionSnapshotStorageFactory:
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


def register_flow_definition_snapshot_storage(
    store_class: type[KeyValueStoragePort],
) -> type[KeyValueStoragePort]:
    """Register a flow definition snapshot storage class via decorator.

    The decorated class must define a ``STORE_BACKEND`` class attribute whose
    value is the string used in YAML config to select this store
    (e.g. ``"filesystem"``, ``"duckdb"``).

    Usage::

        @register_flow_definition_snapshot_storage
        class KeyValueFileSystemStorage(KeyValueStoragePort):
            STORE_BACKEND = "filesystem"
    """
    return FlowDefinitionSnapshotStorageFactory.register(store_class)


# ---------------------------------------------------------------------------
# Internal config helper
# ---------------------------------------------------------------------------


def _resolve_backend_and_config(*, yaml_config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract backend name and merged config dict from a parsed YAML document."""
    global_storage_config = yaml_config.get(DocpipeConfigKeys.GLOBAL_STORAGE, {})
    flow_definition_snapshot_config = yaml_config.get(DocpipeConfigKeys.FLOW_DEFINITION_SNAPSHOT, {})
    storage_config: Any | dict[Any, Any] = flow_definition_snapshot_config.get(DocpipeConfigKeys.STORAGE, {}) or {}

    # Precedence: service-specific > global_storage > default
    backend = (
        storage_config.get(DocpipeConfigKeys.TYPE)
        or global_storage_config.get(DocpipeConfigKeys.TYPE)
        or DEFAULT_STORAGE_BACKEND
    )

    if backend not in FlowDefinitionSnapshotStorageFactory._stores:
        available = ", ".join(FlowDefinitionSnapshotStorageFactory._stores.keys()) or "none"
        raise DocpipeException(
            f"Invalid storage backend '{backend}' for flow definition snapshot storage. Available: {available}"
        )

    # # Merge config: global_storage base, overridden by service-specific block.
    merged: dict[str, Any] = {}
    if global_storage_config:
        merged.update(global_storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})
    merged.update(storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})

    return backend, merged


# ---------------------------------------------------------------------------
# Module-level singleton factory  (mirrors get_default_factory in job_management)
# ---------------------------------------------------------------------------

_default_factory: FlowDefinitionSnapshotStorageFactory | None = None
_default_factory_lock: threading.Lock = threading.Lock()


def get_default_factory() -> FlowDefinitionSnapshotStorageFactory:
    """Return the process-wide singleton ``FlowDefinitionSnapshotStorageFactory``.

    Built once from standard config-file / env-var sources on first call.
    The store and service it owns are also lazy singletons on the factory.
    """
    global _default_factory

    if _default_factory is None:
        with _default_factory_lock:
            if _default_factory is None:
                _default_factory = FlowDefinitionSnapshotStorageFactory.from_default_sources()

    return _default_factory


def get_flow_definitions_snapshot_storage() -> KeyValueStoragePort:
    """
    Return the singleton KeyValueStoragePort adapter for flow definition snapshots.

    Built from the default configuration sources on first call.
    """
    return get_default_factory().get_store()
