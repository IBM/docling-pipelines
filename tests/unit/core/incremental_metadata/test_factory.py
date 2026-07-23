"""Tests for IncrementalMetadataFactory."""

import pytest
import yaml

from docpipe.core.incremental_metadata.adapters.config.incremental_metadata_factory import (
    IncrementalMetadataFactory,
    create_incremental_metadata_store,
    create_store_from_config_file,
    reset_default_incremental_store,
)
from docpipe.core.incremental_metadata.adapters.stores.filesystem import FilesystemIncrementalMetadataStore


class TestIncrementalMetadataFactory:
    """Test IncrementalMetadataFactory registry and create()."""

    def test_create_filesystem_store(self, *, tmp_path):
        """Test creating a filesystem store via the factory."""
        store = IncrementalMetadataFactory.create("filesystem", config={"base_dir": str(tmp_path)})

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._base_dir == tmp_path

    def test_create_store_with_lock_timeout(self, *, tmp_path):
        """Test that config is passed through to the store."""
        store = IncrementalMetadataFactory.create(
            "filesystem", config={"base_dir": str(tmp_path), "lock_timeout": 10.0}
        )

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._lock_timeout == 10.0

    def test_create_unknown_backend_raises_error(self):
        """Test that creating an unknown backend raises DocpipeException."""
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        with pytest.raises(DocpipeException, match="Unknown incremental metadata store backend"):
            IncrementalMetadataFactory.create("duckdb")

    def test_list_backends_contains_registered(self):
        """Test that registered backends appear in list_backends()."""
        backends = IncrementalMetadataFactory.list_backends()
        assert "filesystem" in backends
        assert "postgresql" in backends


class TestCreateStoreFromConfigFile:
    """Test create_store_from_config_file()."""

    def test_filesystem_backend_from_config(self, *, tmp_path):
        """Test creating store from YAML config with filesystem backend."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "incremental_metadata": {
                "storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "metadata")}}
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        store = create_store_from_config_file(config_path=str(config_path))

        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_global_storage_fallback(self, *, tmp_path):
        """Test factory uses global_storage as fallback."""
        config_path = tmp_path / "config.yaml"
        config_data = {"global_storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "global")}}}
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        store = create_store_from_config_file(config_path=str(config_path))

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._base_dir == tmp_path / "global"

    def test_service_specific_overrides_global(self, *, tmp_path):
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

        store = create_store_from_config_file(config_path=str(config_path))

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._base_dir == tmp_path / "specific"

    def test_missing_file_uses_default(self, *, tmp_path):
        """Test graceful fallback when config file doesn't exist."""
        store = create_store_from_config_file(config_path=str(tmp_path / "nonexistent.yaml"))

        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_empty_file_uses_default(self, *, tmp_path):
        """Test graceful fallback on empty config file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")

        store = create_store_from_config_file(config_path=str(config_path))

        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_invalid_backend_raises_error(self, *, tmp_path):
        """Test that an unregistered backend raises DocpipeException."""
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        config_path = tmp_path / "config.yaml"
        config_data = {"incremental_metadata": {"storage": {"type": "duckdb"}}}
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(DocpipeException, match="Invalid storage backend 'duckdb'"):
            create_store_from_config_file(config_path=str(config_path))


class TestCreateIncrementalMetadataStore:
    """Test the primary create_incremental_metadata_store() entry point."""

    def test_returns_filesystem_store_from_config(self, *, tmp_path, monkeypatch):
        """Test convenience function creates store from YAML config."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "incremental_metadata": {
                "storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "metadata")}}
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("DOCPIPE_CONFIG_PATH", str(config_path))
        reset_default_incremental_store()

        store = create_incremental_metadata_store(job_id="test-job")

        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_caching_returns_same_instance(self, *, monkeypatch):
        """Test that repeated calls return the same cached store instance."""
        monkeypatch.delenv("DOCPIPE_CONFIG_PATH", raising=False)
        reset_default_incremental_store()

        store_a = create_incremental_metadata_store()
        store_b = create_incremental_metadata_store()

        assert store_a is store_b

    def test_base_dir_env_override(self, *, tmp_path, monkeypatch):
        """Test DOCPIPE_INCREMENTAL_BASE_DIR is picked up by the filesystem store."""
        env_dir = tmp_path / "env_override"
        monkeypatch.setenv("DOCPIPE_INCREMENTAL_BASE_DIR", str(env_dir))
        reset_default_incremental_store()

        store = create_incremental_metadata_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._base_dir == env_dir
