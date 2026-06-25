"""Tests for IncrementalMetadataFactory."""

import pytest
import yaml

from docpipe.core.incremental_metadata.adapters.config.incremental_metadata_factory import (
    IncrementalMetadataFactory,
    IncrementalStorageBackend,
    create_incremental_metadata_store,
    reset_default_incremental_factory,
)
from docpipe.core.incremental_metadata.adapters.stores.filesystem import FilesystemIncrementalMetadataStore


class TestIncrementalMetadataFactory:
    """Test IncrementalMetadataFactory configuration and creation."""

    def test_create_filesystem_store(self, *, tmp_path):
        """Test creating Filesystem store."""
        factory = IncrementalMetadataFactory(
            storage_backend=IncrementalStorageBackend.FILESYSTEM, config={"base_dir": str(tmp_path)}
        )

        store = factory.create_incremental_metadata_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._base_dir == tmp_path

    def test_create_store_with_lock_timeout(self, *, tmp_path):
        """Test creating store with custom lock timeout."""
        factory = IncrementalMetadataFactory(
            storage_backend=IncrementalStorageBackend.FILESYSTEM,
            config={"base_dir": str(tmp_path), "lock_timeout": 10.0},
        )

        store = factory.create_incremental_metadata_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._lock_timeout == 10.0

    def test_singleton_behavior(self, *, tmp_path):
        """Test that factory returns same store instance."""
        factory = IncrementalMetadataFactory(
            storage_backend=IncrementalStorageBackend.FILESYSTEM, config={"base_dir": str(tmp_path)}
        )

        store1 = factory.create_incremental_metadata_store()
        store2 = factory.create_incremental_metadata_store()

        assert store1 is store2

    def test_from_config_file_filesystem(self, *, tmp_path):
        """Test creating factory from YAML config file with Filesystem backend."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "incremental_metadata": {
                "storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "metadata")}}
            }
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        factory = IncrementalMetadataFactory.from_config_file(str(config_path))

        assert factory.storage_backend == IncrementalStorageBackend.FILESYSTEM

    def test_from_config_file_with_global_storage(self, *, tmp_path):
        """Test factory uses global_storage as fallback."""
        config_path = tmp_path / "config.yaml"
        config_data = {"global_storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "global")}}}

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        factory = IncrementalMetadataFactory.from_config_file(str(config_path))

        assert factory.storage_backend == IncrementalStorageBackend.FILESYSTEM
        assert factory.config["base_dir"] == str(tmp_path / "global")

    def test_from_config_file_service_specific_overrides_global(self, *, tmp_path):
        """Test service-specific config overrides global_storage."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "global_storage": {"type": "postgresql", "config": {"base_dir": str(tmp_path / "global")}},
            "incremental_metadata": {
                "storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "specific")}}
            },
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        factory = IncrementalMetadataFactory.from_config_file(str(config_path))

        assert factory.storage_backend == IncrementalStorageBackend.FILESYSTEM
        assert factory.config["base_dir"] == str(tmp_path / "specific")

    def test_from_config_file_missing_file(self, *, tmp_path):
        """Test graceful handling when config file doesn't exist - uses defaults."""
        factory = IncrementalMetadataFactory.from_config_file(str(tmp_path / "nonexistent.yaml"))
        # Should successfully create a store with default filesystem backend
        store = factory.create_incremental_metadata_store()
        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_from_config_file_invalid_backend(self, *, tmp_path):
        """Test that invalid storage backend raises ValueError."""
        config_path = tmp_path / "config.yaml"
        config_data = {"incremental_metadata": {"storage": {"type": "duckdb"}}}

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # Should raise ValueError for invalid backend
        with pytest.raises(ValueError, match="Invalid storage backend 'duckdb' for incremental metadata"):
            IncrementalMetadataFactory.from_config_file(str(config_path))

    def test_from_config_file_empty_config(self, *, tmp_path):
        """Test handling empty config file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")

        factory = IncrementalMetadataFactory.from_config_file(str(config_path))

        assert factory.storage_backend == IncrementalStorageBackend.FILESYSTEM

    def test_from_environment(self, *, monkeypatch):
        """Test creating factory from environment variables."""
        monkeypatch.setenv("DOCPIPE_INCREMENTAL_STORAGE_BACKEND", "filesystem")

        factory = IncrementalMetadataFactory.from_environment()

        assert factory.storage_backend == IncrementalStorageBackend.FILESYSTEM

    def test_from_environment_invalid_backend(self, *, monkeypatch):
        """Test that invalid backend in environment raises ValueError."""
        monkeypatch.setenv("DOCPIPE_INCREMENTAL_STORAGE_BACKEND", "duckdb")

        # Should raise ValueError for invalid backend
        with pytest.raises(ValueError, match="Invalid storage backend 'duckdb' for incremental metadata"):
            IncrementalMetadataFactory.from_environment()

    def test_from_environment_defaults(self):
        """Test from_environment uses defaults when no env vars set."""
        factory = IncrementalMetadataFactory.from_environment()

        assert factory.storage_backend == IncrementalStorageBackend.FILESYSTEM

    def test_environment_override_in_from_default_sources(self, *, tmp_path, monkeypatch):
        """Test environment variable overrides config file."""
        config_path = tmp_path / "config.yaml"
        config_data = {"incremental_metadata": {"storage": {"type": "filesystem"}}}

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("DOCPIPE_CONFIG_PATH", str(config_path))
        monkeypatch.setenv("DOCPIPE_INCREMENTAL_STORAGE_BACKEND", "filesystem")

        factory = IncrementalMetadataFactory.from_default_sources()

        assert factory.storage_backend == IncrementalStorageBackend.FILESYSTEM

    def test_base_dir_environment_override(self, *, tmp_path, monkeypatch):
        """Test DOCPIPE_INCREMENTAL_BASE_DIR overrides config."""
        monkeypatch.setenv("DOCPIPE_INCREMENTAL_BASE_DIR", str(tmp_path / "env_override"))

        factory = IncrementalMetadataFactory(
            storage_backend=IncrementalStorageBackend.FILESYSTEM, config={"base_dir": str(tmp_path / "config")}
        )

        store = factory.create_incremental_metadata_store()

        assert store._base_dir == tmp_path / "env_override"

    def test_create_incremental_metadata_store_function(self, *, tmp_path, monkeypatch):
        """Test convenience function for creating store."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "incremental_metadata": {
                "storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "metadata")}}
            }
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("DOCPIPE_CONFIG_PATH", str(config_path))
        reset_default_incremental_factory()

        store = create_incremental_metadata_store(job_id="test-job")

        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_invalid_storage_backend_raises_error(self, *, tmp_path):
        """Test that invalid storage backend raises error."""
        factory = IncrementalMetadataFactory(storage_backend="invalid_type", config={})  # type: ignore

        with pytest.raises(ValueError, match="Unknown storage backend"):
            factory.create_incremental_metadata_store()
