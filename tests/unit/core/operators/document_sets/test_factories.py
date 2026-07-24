"""Unit tests for document set factories."""

# Import to trigger adapter registration
import pytest

import docpipe.core.assets.document_sets.adapters.duckdb  # noqa: F401
from docpipe.core.assets.document_sets.domain.types import DataStoreConfig
from docpipe.core.assets.document_sets.factories import (
    DataStoreFactory,
    MetadataRepositoryFactory,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException


class TestMetadataRepositoryFactory:
    """Test MetadataRepositoryFactory."""

    def test_list_adapters(self):
        """Test listing registered adapters."""
        adapters = MetadataRepositoryFactory.list_adapters()
        assert len(adapters) > 0
        assert any(a["name"] == "duckdb" for a in adapters)

        # Verify adapter metadata structure
        duckdb_adapter = next(a for a in adapters if a["name"] == "duckdb")
        assert "display_name" in duckdb_adapter
        assert "class" in duckdb_adapter
        assert duckdb_adapter["display_name"] == "DuckDB"

    def test_create_duckdb_adapter(self, *, tmp_path):
        """Test creating DuckDB adapter."""
        config = {"database_path": str(tmp_path / "test.db")}
        repository = MetadataRepositoryFactory.create(adapter_name="duckdb", config=config)

        assert repository is not None
        assert hasattr(repository, "create")
        assert hasattr(repository, "get_by_id")
        assert hasattr(repository, "update")
        assert hasattr(repository, "delete")

    def test_create_duckdb_adapter_memory(self):
        """Test creating DuckDB adapter with in-memory database."""
        config = {"database_path": ":memory:"}
        repository = MetadataRepositoryFactory.create(adapter_name="duckdb", config=config)

        assert repository is not None

    def test_create_unknown_adapter(self):
        """Test creating unknown adapter raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            MetadataRepositoryFactory.create(adapter_name="unknown_adapter", config={"database_path": "test.db"})

        assert exc_info.value.status_code == 400
        assert "unknown_adapter" in str(exc_info.value).lower()

    def test_create_invalid_config_missing_path(self):
        """Test creating adapter with missing database_path raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            MetadataRepositoryFactory.create(adapter_name="duckdb", config={})

        assert exc_info.value.status_code == 400
        assert "database_path" in str(exc_info.value).lower()

    def test_create_invalid_config_empty_path(self):
        """Test creating adapter with empty database_path raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            MetadataRepositoryFactory.create(adapter_name="duckdb", config={"database_path": ""})

        assert exc_info.value.status_code == 400

    def test_create_invalid_config_wrong_type(self):
        """Test creating adapter with wrong type for database_path raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            MetadataRepositoryFactory.create(adapter_name="duckdb", config={"database_path": 123})  # type: ignore

        assert exc_info.value.status_code == 400

    def test_get_adapter_info(self):
        """Test getting adapter information."""
        info = MetadataRepositoryFactory.get_adapter_info(adapter_name="duckdb")

        assert info["name"] == "duckdb"
        assert info["display_name"] == "DuckDB"
        assert "class" in info

    def test_get_adapter_info_unknown(self):
        """Test getting info for unknown adapter raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            MetadataRepositoryFactory.get_adapter_info(adapter_name="unknown")

        assert exc_info.value.status_code == 400


class TestDataStoreFactory:
    """Test DataStoreFactory."""

    def test_list_adapters(self):
        """Test listing registered adapters."""
        adapters = DataStoreFactory.list_adapters()
        assert len(adapters) > 0
        assert any(a["name"] == "duckdb" for a in adapters)

        # Verify adapter metadata structure
        duckdb_adapter = next(a for a in adapters if a["name"] == "duckdb")
        assert "display_name" in duckdb_adapter
        assert "class" in duckdb_adapter
        assert duckdb_adapter["display_name"] == "DuckDB"

    def test_create_duckdb_adapter(self, *, tmp_path):
        """Test creating DuckDB adapter."""
        config: DataStoreConfig = {"database_path": str(tmp_path / "test.db")}
        data_store = DataStoreFactory.create(adapter_name="duckdb", config=config)

        assert data_store is not None
        assert hasattr(data_store, "create_data_table")
        assert hasattr(data_store, "upsert_document_set_data")
        assert hasattr(data_store, "get_document_set_data")
        assert hasattr(data_store, "delete_document_set_data")

    def test_create_duckdb_adapter_memory(self):
        """Test creating DuckDB adapter with in-memory database."""
        config: DataStoreConfig = {"database_path": ":memory:"}
        data_store = DataStoreFactory.create(adapter_name="duckdb", config=config)

        assert data_store is not None

    def test_create_unknown_adapter(self):
        """Test creating unknown adapter raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            DataStoreFactory.create(adapter_name="unknown_adapter", config={"database_path": "test.db"})

        assert exc_info.value.status_code == 400
        assert "unknown_adapter" in str(exc_info.value).lower()

    def test_create_invalid_config_missing_path(self):
        """Test creating adapter with missing database_path raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            DataStoreFactory.create(adapter_name="duckdb", config={})

        assert exc_info.value.status_code == 400
        assert "database_path" in str(exc_info.value).lower()

    def test_create_invalid_config_empty_path(self):
        """Test creating adapter with empty database_path raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            DataStoreFactory.create(adapter_name="duckdb", config={"database_path": ""})

        assert exc_info.value.status_code == 400

    def test_create_invalid_config_wrong_type(self):
        """Test creating adapter with wrong type for database_path raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            DataStoreFactory.create(adapter_name="duckdb", config={"database_path": 123})

        assert exc_info.value.status_code == 400

    def test_get_adapter_info(self):
        """Test getting adapter information."""
        info = DataStoreFactory.get_adapter_info(adapter_name="duckdb")

        assert info["name"] == "duckdb"
        assert info["display_name"] == "DuckDB"
        assert "class" in info

    def test_get_adapter_info_unknown(self):
        """Test getting info for unknown adapter raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            DataStoreFactory.get_adapter_info(adapter_name="unknown")

        assert exc_info.value.status_code == 400
