"""
ContentStorageFactory — factory for content storage adapters used by report generation.

Creates the appropriate ContentStoragePort implementation based on the
`job_run_report.storage` section of docling-pipelines-config.yaml.

docling-pipelines ships with ContentFileSystemStorage.
Additional storage backends can be registered at import time.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

from docpipe.core.constants import DocpipeConfigKeys
from docpipe.core.constants.constants import EnvironmentVariables, _find_project_root
from docpipe.storage.file_system.content_file_system_storage import ContentFileSystemStorage
from docpipe.storage.interfaces.content_storage_port import ContentStoragePort
from docpipe.utils.infrastructure.filesystem import get_data_path
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


@runtime_checkable
class _ContentStorageConstructor(Protocol):
    """Protocol for ContentStoragePort implementations that accept ``base_dir``."""

    def __call__(self, *, base_dir: str) -> ContentStoragePort: ...


class ContentStorageType(StrEnum):
    """Supported content storage backends."""

    FILESYSTEM = "filesystem"


# Registry mapping storage type strings to ContentStoragePort implementations.
# Additional backends can be registered at import time:
#
#   from docpipe.core.job_management.adapters.config.report_storage_factory import (
#       CONTENT_STORAGE_REGISTRY,
#   )
#   CONTENT_STORAGE_REGISTRY["cos"] = COSContentStorage
#
CONTENT_STORAGE_REGISTRY: dict[str, _ContentStorageConstructor] = {
    ContentStorageType.FILESYSTEM: ContentFileSystemStorage,  # type: ignore[dict-item]
}


class ContentStorageFactory:
    """
    Registry-based factory for instantiating ContentStoragePort adapters.

    Configuration is read from the ``job_run_report.storage`` section of
    docling-pipelines-config.yaml:

    .. code-block:: yaml

        job_run_report:
          storage:
            type: filesystem
            config:
              data_root: ./data

    Additional backends are registered in CONTENT_STORAGE_REGISTRY before
    the factory is instantiated.

    Usage::

        adapter = ContentStorageFactory().create_storage()
        content = adapter.read_text(collection=job_id, file_name="report.csv")
    """

    def __init__(
        self,
        *,
        storage_type: ContentStorageType = ContentStorageType.FILESYSTEM,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.storage_type = storage_type
        self.config = config or {}

    def create_storage(self) -> ContentStoragePort:
        """
        Instantiate the configured ContentStoragePort adapter.

        Returns:
            ContentStoragePort implementation

        Raises:
            ValueError: If the storage type is not registered
        """
        adapter_constructor = CONTENT_STORAGE_REGISTRY.get(self.storage_type)
        if adapter_constructor is None:
            supported = list(CONTENT_STORAGE_REGISTRY.keys())
            raise ValueError(f"Unknown content storage type '{self.storage_type}'. Supported: {supported}")

        data_root = self.config.get("data_root") or get_data_path()
        adapter = adapter_constructor(base_dir=str(data_root))
        logger.info("Created %s for content storage", type(adapter).__name__)
        return adapter

    @classmethod
    def from_config_file(cls, config_path: str) -> ContentStorageFactory:
        """
        Build a factory from a YAML configuration file.

        Reads the ``job_run_report.storage`` section.
        Falls back to the filesystem adapter with defaults when absent.
        """
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning("Config file not found at %s, using default filesystem content storage", config_path)
            return cls()

        try:
            with open(config_file) as f:
                yaml_config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}") from e

        report_section = yaml_config.get(DocpipeConfigKeys.JOB_RUN_REPORT, {}) or {}
        storage_section = report_section.get(DocpipeConfigKeys.STORAGE, {}) or {}

        storage_type_str = storage_section.get(DocpipeConfigKeys.TYPE, ContentStorageType.FILESYSTEM.value)
        storage_config = storage_section.get(DocpipeConfigKeys.CONFIG, {}) or {}

        try:
            storage_type = ContentStorageType(storage_type_str)
        except ValueError:
            supported = [e.value for e in ContentStorageType]
            raise ValueError(f"Invalid content storage type '{storage_type_str}'. Supported: {supported}") from None

        logger.info("Loaded content storage configuration from %s: type=%s", config_path, storage_type)
        return cls(storage_type=storage_type, config=storage_config)

    @classmethod
    def from_default_sources(cls) -> ContentStorageFactory:
        """
        Build a factory from the default config file location.

        Reads DOCPIPE_CONFIG_PATH env var for a custom config path.
        Falls back to ``{project_root}/docling-pipelines-config.yaml`` when the
        env var is not set.
        """
        default_config_path = _find_project_root() / "docling-pipelines-config.yaml"
        config_path = Path(os.getenv(EnvironmentVariables.DOCPIPE_CONFIG_PATH, str(default_config_path)))
        if config_path.exists():
            return cls.from_config_file(str(config_path))

        logger.warning("Config file not found at %s. Using default filesystem content storage.", config_path)
        return cls()


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------

_default_factory: ContentStorageFactory | None = None
_default_adapter: ContentStoragePort | None = None


def get_report_storage() -> ContentStoragePort:
    """
    Return the singleton ContentStoragePort adapter.

    Built from the default configuration sources on first call.
    """
    global _default_factory, _default_adapter

    if _default_adapter is None:
        if _default_factory is None:
            _default_factory = ContentStorageFactory.from_default_sources()
        _default_adapter = _default_factory.create_storage()

    return _default_adapter


def reset_report_storage() -> None:
    """Reset singleton instances (useful for testing)."""
    global _default_factory, _default_adapter
    _default_factory = None
    _default_adapter = None
