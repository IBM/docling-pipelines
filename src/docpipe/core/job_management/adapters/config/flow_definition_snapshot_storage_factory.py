"""
FlowDefinitionSnapshotStorageFactory — factory for key-value storage adapters used by flow definition snapshots.

Creates the appropriate KeyValueStoragePort implementation based on the
``flow_definition_snapshot.storage`` section of docling-pipelines-config.yaml.

Flow definitions are JSON objects, so KeyValueStoragePort is the right abstraction:
it natively serialises/deserialises dicts to/from JSON files without any manual
json.dumps / json.loads round-trips.

docling-pipelines ships with KeyValueFileSystemStorage.
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
from docpipe.storage.file_system.key_value_file_system_storage import KeyValueFileSystemStorage
from docpipe.storage.interfaces.key_value_storage_port import KeyValueStoragePort
from docpipe.utils.infrastructure.filesystem import get_data_path
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


@runtime_checkable
class _KeyValueStorageConstructor(Protocol):
    """Protocol for KeyValueStoragePort implementations that accept ``base_dir``."""

    def __call__(self, *, base_dir: str) -> KeyValueStoragePort: ...


class FlowDefinitionSnapshotStorageType(StrEnum):
    """Supported storage backends for flow definition snapshots."""

    FILESYSTEM = "filesystem"


# Registry mapping storage type strings to KeyValueStoragePort implementations.
# Additional backends can be registered at import time:
#
#   from docpipe.core.job_management.adapters.config.flow_definition_snapshot_storage_factory import (
#       FLOW_DEFINITION_SNAPSHOT_STORAGE_REGISTRY,
#   )
#   FLOW_DEFINITION_SNAPSHOT_STORAGE_REGISTRY["cos"] = COSKeyValueStorage
#
FLOW_DEFINITION_SNAPSHOT_STORAGE_REGISTRY: dict[str, _KeyValueStorageConstructor] = {
    FlowDefinitionSnapshotStorageType.FILESYSTEM: KeyValueFileSystemStorage,  # type: ignore[dict-item]
}


class FlowDefinitionSnapshotStorageFactory:
    """
    Registry-based factory for instantiating KeyValueStoragePort adapters for flow definition snapshots.

    Configuration is read from the ``flow_definition_snapshot.storage`` section of
    docling-pipelines-config.yaml:

    .. code-block:: yaml

        flow_definition_snapshot:
          storage:
            type: filesystem
            config:
              base_dir: ./data

    Because flow definitions are JSON objects, ``KeyValueStoragePort`` is used instead of
    ``ContentStoragePort`` — it natively handles dict serialisation and deserialisation.

    Additional backends are registered in FLOW_DEFINITION_SNAPSHOT_STORAGE_REGISTRY before
    the factory is instantiated.

    Usage::

        adapter = FlowDefinitionSnapshotStorageFactory().create_storage()
        adapter.save_record(collection=f"{job_id}/{job_run_id}", key="flow_definition", data=flow_dict)
        record = adapter.get_record(collection=f"{job_id}/{job_run_id}", key="flow_definition")
    """

    def __init__(
        self,
        *,
        storage_type: FlowDefinitionSnapshotStorageType = FlowDefinitionSnapshotStorageType.FILESYSTEM,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.storage_type = storage_type
        self.config = config or {}

    def create_storage(self) -> KeyValueStoragePort:
        """
        Instantiate the configured KeyValueStoragePort adapter.

        Returns:
            KeyValueStoragePort implementation

        Raises:
            ValueError: If the storage type is not registered
        """
        adapter_constructor = FLOW_DEFINITION_SNAPSHOT_STORAGE_REGISTRY.get(self.storage_type)
        if adapter_constructor is None:
            supported = list(FLOW_DEFINITION_SNAPSHOT_STORAGE_REGISTRY.keys())
            raise ValueError(
                f"Unknown flow definition snapshot storage type '{self.storage_type}'. Supported: {supported}"
            )

        base_dir = self.config.get("base_dir") or get_data_path()
        adapter = adapter_constructor(base_dir=str(base_dir))
        logger.info("Created %s for flow definition snapshot storage", type(adapter).__name__)
        return adapter

    @classmethod
    def from_config_file(cls, config_path: str) -> FlowDefinitionSnapshotStorageFactory:
        """
        Build a factory from a YAML configuration file.

        Reads the ``flow_definition_snapshot.storage`` section.
        Falls back to the filesystem adapter with defaults when absent.
        """
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(
                "Config file not found at %s, using default filesystem flow definition snapshot storage",
                config_path,
            )
            return cls()

        try:
            with open(config_file) as f:
                yaml_config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}") from e

        snapshot_section = yaml_config.get(DocpipeConfigKeys.FLOW_DEFINITION_SNAPSHOT, {}) or {}
        storage_section = snapshot_section.get(DocpipeConfigKeys.STORAGE, {}) or {}

        storage_type_str = storage_section.get(
            DocpipeConfigKeys.TYPE, FlowDefinitionSnapshotStorageType.FILESYSTEM.value
        )
        storage_config = storage_section.get(DocpipeConfigKeys.CONFIG, {}) or {}

        try:
            storage_type = FlowDefinitionSnapshotStorageType(storage_type_str)
        except ValueError:
            supported = [e.value for e in FlowDefinitionSnapshotStorageType]
            raise ValueError(
                f"Invalid flow definition snapshot storage type '{storage_type_str}'. Supported: {supported}"
            ) from None

        logger.info("Loaded flow definition snapshot storage configuration from %s: type=%s", config_path, storage_type)
        return cls(storage_type=storage_type, config=storage_config)

    @classmethod
    def from_default_sources(cls) -> FlowDefinitionSnapshotStorageFactory:
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

        logger.warning(
            "Config file not found at %s. Using default filesystem flow definition snapshot storage.", config_path
        )
        return cls()


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------

_default_factory: FlowDefinitionSnapshotStorageFactory | None = None
_default_adapter: KeyValueStoragePort | None = None


def get_flow_definitions_snapshot_storage() -> KeyValueStoragePort:
    """
    Return the singleton KeyValueStoragePort adapter for flow definition snapshots.

    Built from the default configuration sources on first call.
    """
    global _default_factory, _default_adapter

    if _default_adapter is None:
        if _default_factory is None:
            _default_factory = FlowDefinitionSnapshotStorageFactory.from_default_sources()
        _default_adapter = _default_factory.create_storage()

    return _default_adapter


def reset_file_definitions_snapshot_storage() -> None:
    """Reset singleton instances (useful for testing)."""
    global _default_factory, _default_adapter
    _default_factory = None
    _default_adapter = None
