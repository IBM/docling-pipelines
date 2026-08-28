"""Tests for IncrementalMetadataFactory."""

from pathlib import Path

import pytest
import yaml

import docpipe.core.incremental_metadata.adapters.config.incremental_metadata_factory as _factory_mod
from docpipe.core.incremental_metadata.adapters.config.incremental_metadata_factory import (
    IncrementalMetadataFactory,
    get_default_factory,
)
from docpipe.core.incremental_metadata.adapters.stores.filesystem import FilesystemIncrementalMetadataStore


class TestIncrementalMetadataFactory:
    """Test IncrementalMetadataFactory registry and get_store()."""

    def test_create_filesystem_store(self, *, tmp_path):
        """Test creating a filesystem store via the factory instance."""
        factory = IncrementalMetadataFactory(backend="filesystem", config={"base_dir": str(tmp_path)})
        store = factory.get_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._base_dir == tmp_path

    def test_create_store_with_lock_timeout(self, *, tmp_path):
        """Test that config is passed through to the store."""
        factory = IncrementalMetadataFactory(
            backend="filesystem", config={"base_dir": str(tmp_path), "lock_timeout": 10.0}
        )
        store = factory.get_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._lock_timeout == 10.0

    def test_get_store_returns_singleton(self, *, tmp_path):
        """get_store() returns the same instance on repeated calls."""
        factory = IncrementalMetadataFactory(backend="filesystem", config={"base_dir": str(tmp_path)})

        assert factory.get_store() is factory.get_store()

    def test_get_service_returns_singleton(self, *, tmp_path):
        """get_service() returns the same instance on repeated calls."""
        factory = IncrementalMetadataFactory(backend="filesystem", config={"base_dir": str(tmp_path)})

        assert factory.get_service() is factory.get_service()

    def test_create_unknown_backend_raises_error(self):
        """Test that get_store() with an unknown backend raises DocpipeException."""
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        factory = IncrementalMetadataFactory(backend="duckdb")
        with pytest.raises(DocpipeException, match="Unknown incremental metadata store backend"):
            factory.get_store()

    def test_list_backends_contains_registered(self):
        """Test that registered backends appear in list_backends()."""
        backends = IncrementalMetadataFactory.list_backends()
        assert "filesystem" in backends
        assert "postgresql" in backends


class TestFromConfigFile:
    """Test IncrementalMetadataFactory.from_config_file()."""

    def test_filesystem_backend_from_config(self, *, tmp_path):
        """Test creating factory from YAML config with filesystem backend."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "incremental_metadata": {
                "storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "metadata")}}
            }
        }
        with Path(config_path).open("w") as f:
            yaml.dump(config_data, f)

        factory = IncrementalMetadataFactory.from_config_file(config_path=str(config_path))
        store = factory.get_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_global_storage_fallback(self, *, tmp_path):
        """Test factory uses global_storage as fallback."""
        config_path = tmp_path / "config.yaml"
        config_data = {"global_storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "global")}}}
        with Path(config_path).open("w") as f:
            yaml.dump(config_data, f)

        factory = IncrementalMetadataFactory.from_config_file(config_path=str(config_path))
        store = factory.get_store()

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
        with Path(config_path).open("w") as f:
            yaml.dump(config_data, f)

        factory = IncrementalMetadataFactory.from_config_file(config_path=str(config_path))
        store = factory.get_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._base_dir == tmp_path / "specific"

    def test_missing_file_uses_default(self, *, tmp_path):
        """Test graceful fallback when config file doesn't exist."""
        factory = IncrementalMetadataFactory.from_config_file(config_path=str(tmp_path / "nonexistent.yaml"))
        store = factory.get_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_empty_file_uses_default(self, *, tmp_path):
        """Test graceful fallback on empty config file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")

        factory = IncrementalMetadataFactory.from_config_file(config_path=str(config_path))
        store = factory.get_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_invalid_backend_raises_error(self, *, tmp_path):
        """Test that an unregistered backend raises DocpipeException."""
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        config_path = tmp_path / "config.yaml"
        config_data = {"incremental_metadata": {"storage": {"type": "duckdb"}}}
        with Path(config_path).open("w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(DocpipeException, match="Invalid storage backend 'duckdb'"):
            IncrementalMetadataFactory.from_config_file(config_path=str(config_path))


class TestGetDefaultFactory:
    """Test the process-wide singleton get_default_factory()."""

    def test_returns_filesystem_store_from_config(self, *, tmp_path, monkeypatch):
        """Singleton factory creates store from YAML config."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "incremental_metadata": {
                "storage": {"type": "filesystem", "config": {"base_dir": str(tmp_path / "metadata")}}
            }
        }
        with Path(config_path).open("w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("DOCPIPE_CONFIG_PATH", str(config_path))
        monkeypatch.setattr(_factory_mod, "_default_factory", None)

        store = get_default_factory().get_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)

    def test_caching_returns_same_factory_instance(self, *, monkeypatch):
        """Repeated calls to get_default_factory() return the same instance."""
        monkeypatch.delenv("DOCPIPE_CONFIG_PATH", raising=False)
        monkeypatch.setattr(_factory_mod, "_default_factory", None)

        assert get_default_factory() is get_default_factory()

    def test_store_singleton_across_calls(self, *, monkeypatch):
        """get_store() on the singleton factory always returns the same store."""
        monkeypatch.delenv("DOCPIPE_CONFIG_PATH", raising=False)
        monkeypatch.setattr(_factory_mod, "_default_factory", None)

        store_a = get_default_factory().get_store()
        store_b = get_default_factory().get_store()

        assert store_a is store_b

    def test_base_dir_env_override(self, *, tmp_path, monkeypatch):
        """Test DOCPIPE_INCREMENTAL_BASE_DIR is picked up by the filesystem store."""
        env_dir = tmp_path / "env_override"
        monkeypatch.setenv("DOCPIPE_INCREMENTAL_BASE_DIR", str(env_dir))
        monkeypatch.setattr(_factory_mod, "_default_factory", None)

        store = get_default_factory().get_store()

        assert isinstance(store, FilesystemIncrementalMetadataStore)
        assert store._base_dir == env_dir
