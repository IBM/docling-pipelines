"""
ContentStorageFactory — factory for content storage adapters used by report generation.

Creates the appropriate ContentStoragePort implementation based on the
`job_run_report.storage` section of docling-pipelines-config.yaml.

docling-pipelines ships with ContentFileSystemStorage.
Additional storage backends can be registered at import time.
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
from docpipe.storage.file_system.content_file_system_storage import ContentFileSystemStorage
from docpipe.utils.infrastructure.filesystem import get_data_path
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

DEFAULT_STORAGE_BACKEND = "filesystem"
DEFAULT_CONFIG_PATH = _find_project_root() / "docling-pipelines-config.yaml"
ENV_CONFIG_PATH_KEY = EnvironmentVariables.DOCPIPE_CONFIG_PATH

if TYPE_CHECKING:
    from docpipe.storage.interfaces.content_storage_port import ContentStoragePort


class ContentStorageFactory:
    """Adapter registry for report content storage."""

    _stores: ClassVar[dict[str, type[ContentStoragePort]]] = {
        DEFAULT_STORAGE_BACKEND: ContentFileSystemStorage,
    }

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered backends. Intended for test teardown only."""
        cls._stores.clear()

    @classmethod
    def register(cls, store_class: type[ContentStoragePort]) -> type[ContentStoragePort]:
        """Register a content storage class."""
        if not hasattr(store_class, "STORAGE_BACKEND"):
            raise TypeError(f"Content storage class {store_class.__name__} must define STORAGE_BACKEND")

        backend_name: str = store_class.STORAGE_BACKEND  # type: ignore[attr-defined]

        if backend_name in cls._stores:
            logger.warning("Content storage backend '%s' is already registered. Overwriting.", backend_name)

        cls._stores[backend_name] = store_class
        logger.debug("Registered content storage backend: %s", backend_name)
        return store_class

    @classmethod
    def list_backends(cls) -> list[str]:
        """Return all registered backend names."""
        return list(cls._stores.keys())

    def __init__(self, *, backend: str, config: dict[str, Any] | None = None) -> None:
        self._backend = backend
        self._config: dict[str, Any] = config or {}
        self._store: ContentStoragePort | None = None

    def get_store(self) -> ContentStoragePort:
        """Return the singleton store, creating it on first call."""
        if self._store is None:
            if self._backend not in ContentStorageFactory._stores:
                available = ", ".join(ContentStorageFactory._stores.keys()) or "none"
                raise DocpipeException(
                    f"Unknown report content storage backend: '{self._backend}'. Available backends: {available}"
                )

            store_class = ContentStorageFactory._stores[self._backend]
            base_dir = self._config.get("data_root") or self._config.get(DocpipeConfigKeys.BASE_DIR) or get_data_path()
            self._store = store_class(base_dir=str(base_dir))  # type: ignore[call-arg]
            logger.info("Created report content storage: backend=%s", self._backend)
        return self._store

    @classmethod
    def from_config_file(cls, *, config_path: str) -> ContentStorageFactory:
        """Build a factory from a YAML configuration file."""
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning("Config file not found: %s. Using default report storage configuration.", config_path)
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
        logger.info("Report storage factory from %s: backend=%s", config_path, backend)
        return cls(backend=backend, config=config)

    @classmethod
    def from_default_sources(cls) -> ContentStorageFactory:
        """Build a factory from the standard config-file / env-var path."""
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
    def _default_backend_factory(cls) -> ContentStorageFactory:
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


def register_content_storage(store_class: type[ContentStoragePort]) -> type[ContentStoragePort]:
    """Register a ContentStoragePort implementation via decorator."""
    return ContentStorageFactory.register(store_class)


# ---------------------------------------------------------------------------
# Internal config helper
# ---------------------------------------------------------------------------


def _resolve_backend_and_config(*, yaml_config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract backend name and merged config dict from a parsed YAML document."""
    global_storage_config = yaml_config.get(DocpipeConfigKeys.GLOBAL_STORAGE, {})
    report_config = yaml_config.get(DocpipeConfigKeys.JOB_RUN_REPORT, {})
    storage_config: Any | dict[Any, Any] = report_config.get(DocpipeConfigKeys.STORAGE, {}) or {}

    backend = (
        storage_config.get(DocpipeConfigKeys.TYPE)
        or global_storage_config.get(DocpipeConfigKeys.TYPE)
        or DEFAULT_STORAGE_BACKEND
    )

    available_backends = ContentStorageFactory.list_backends()
    if backend not in available_backends:
        available = ", ".join(available_backends) or "none"
        raise DocpipeException(f"Invalid report storage backend '{backend}'. Available: {available}")

    merged: dict[str, Any] = {}
    if global_storage_config:
        merged.update(global_storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})
    merged.update(storage_config.get(DocpipeConfigKeys.CONFIG, {}) or {})

    return backend, merged


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------

_default_factory: ContentStorageFactory | None = None
_default_factory_lock: threading.Lock = threading.Lock()


def get_default_factory() -> ContentStorageFactory:
    """Return the process-wide singleton ``ContentStorageFactory``."""
    global _default_factory

    if _default_factory is None:
        with _default_factory_lock:
            if _default_factory is None:
                _default_factory = ContentStorageFactory.from_default_sources()

    return _default_factory


def get_report_storage() -> ContentStoragePort:
    """Return the singleton ContentStoragePort adapter for report generation."""
    return get_default_factory().get_store()


def reset_report_storage() -> None:
    """Reset singleton instances (useful for testing)."""
    global _default_factory
    _default_factory = None
