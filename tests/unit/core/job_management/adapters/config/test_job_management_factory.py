"""
Tests for JobManagementFactory configuration and store selection.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.job_management.adapters.config import (
    FrameworkType,
    JobManagementFactory,
    StorageBackend,
)


class TestJobManagementFactoryStoreSelection:
    """Test factory store selection logic."""

    def test_inmemory_store_creation(self):
        """Test InMemoryJobStatsStore creation."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        store = factory.create_job_stats_store()

        assert store is not None
        assert store.__class__.__name__ == "InMemoryJobStatsStore"

    def test_filesystem_store_creation(self):
        """Test JsonJobStatsStore creation."""
        factory = JobManagementFactory(storage_backend=StorageBackend.FILESYSTEM)
        store = factory.create_job_stats_store()

        assert store is not None
        assert store.__class__.__name__ == "JsonJobStatsStore"

    @patch("docpipe.core.job_management.adapters.config.job_management_factory.run_migrations")
    @patch("docpipe.core.job_management.adapters.stores.postgres.postgres_job_stats_store.create_session_factory")
    @patch("docpipe.core.job_management.adapters.stores.postgres.postgres_job_stats_store.create_postgres_engine")
    @patch(
        "docpipe.core.job_management.adapters.stores.postgres.postgres_job_stats_store.get_postgres_connection_string"
    )
    def test_postgresql_store_creation_with_config(
        self, mock_conn_string, mock_engine, mock_session_factory, mock_run_migrations
    ):
        """Test PostgresJobStatsStore creation with config."""
        # Mock successful PostgreSQL setup
        mock_conn_string.return_value = (
            "postgresql+psycopg2://user:pass@localhost:5432/docpipe"  # pragma: allowlist secret
        )
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_session_factory.return_value = MagicMock()

        config = {
            "postgres": {
                "host": "localhost",
                "port": 5432,
                "database": "docpipe",
                "user": "test_user",
                "password": os.environ.get("TEST_DB_PASSWORD", "test-db-pw"),
            }
        }

        factory = JobManagementFactory(storage_backend=StorageBackend.POSTGRESQL, config=config)
        store = factory.create_job_stats_store()

        assert store is not None
        assert store.__class__.__name__ == "PostgresJobStatsStore"
        mock_conn_string.assert_called_once_with(config=config)
        mock_engine.assert_called_once()
        mock_session_factory.assert_called_once_with(engine=mock_engine_instance)

    def test_postgresql_store_creation_without_password_raises_error(self):
        """Test PostgresJobStatsStore creation fails without password."""
        factory = JobManagementFactory(storage_backend=StorageBackend.POSTGRESQL)

        from docpipe.exceptions.docpipe_exceptions import (
            JobStatsStoreInitializationException,
        )

        with pytest.raises(
            JobStatsStoreInitializationException,
            match="PostgreSQL connection not configured",
        ):
            factory.create_job_stats_store()

    def test_singleton_behavior(self):
        """Test that factory returns same store instance."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)

        store1 = factory.create_job_stats_store()
        store2 = factory.create_job_stats_store()

        assert store1 is store2

    def test_from_environment_postgresql(self):
        """Test factory creation from environment variables."""
        with patch.dict(
            os.environ,
            {
                "DOCPIPE_STORAGE_BACKEND": "postgresql",
                "DOCPIPE_FRAMEWORK_TYPE": "default",
            },
        ):
            factory = JobManagementFactory.from_environment()

            assert factory.storage_backend == StorageBackend.POSTGRESQL
            assert factory.framework_type == FrameworkType.DEFAULT

    def test_from_environment_defaults(self):
        """Test factory creation with default values."""
        with patch.dict(os.environ, {}, clear=True):
            factory = JobManagementFactory.from_environment()

            assert factory.storage_backend == StorageBackend.IN_MEMORY
            assert factory.framework_type == FrameworkType.DEFAULT

    def test_from_environment_invalid_backend_raises_error(self):
        """Test invalid storage backend raises ValueError."""
        with patch.dict(os.environ, {"DOCPIPE_STORAGE_BACKEND": "invalid_backend"}):
            with pytest.raises(ValueError, match="Invalid DOCPIPE_STORAGE_BACKEND"):
                JobManagementFactory.from_environment()


class TestJobManagementFactoryExtended:
    """Extended tests for JobManagementFactory to cover missing lines."""

    def test_duckdb_store_creation(self, tmp_path):
        """Test DuckDBJobStatsStore creation."""
        config = {"database_path": str(tmp_path / "test.duckdb")}
        factory = JobManagementFactory(storage_backend=StorageBackend.DUCKDB, config=config)
        store = factory.create_job_stats_store()

        assert store is not None
        assert store.__class__.__name__ == "DuckDBJobStatsStore"

    def test_filesystem_store_with_env_base_dir(self, tmp_path):
        """Test JsonJobStatsStore creation uses environment base_dir override."""
        with patch.dict(os.environ, {"DOCPIPE_JOB_STATS_BASE_DIR": str(tmp_path)}):
            factory = JobManagementFactory(storage_backend=StorageBackend.FILESYSTEM)
            store = factory.create_job_stats_store()
            assert store.__class__.__name__ == "JsonJobStatsStore"

    def test_filesystem_store_with_configured_base_dir(self, tmp_path):
        """Test JsonJobStatsStore creation uses config base_dir."""
        from docpipe.core.job_management.adapters.config.job_management_factory import DocpipeConfigKeys

        config = {DocpipeConfigKeys.BASE_DIR: str(tmp_path)}
        factory = JobManagementFactory(storage_backend=StorageBackend.FILESYSTEM, config=config)
        store = factory.create_job_stats_store()
        assert store.__class__.__name__ == "JsonJobStatsStore"

    def test_create_job_stats_service(self):
        """Test create_job_stats_service creates a JobTrackerService."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        service = factory.create_job_stats_service()
        assert service is not None

    def test_create_job_stats_service_singleton(self):
        """Test create_job_stats_service returns same instance."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        service1 = factory.create_job_stats_service()
        service2 = factory.create_job_stats_service()
        assert service1 is service2

    def test_create_node_stats_aggregator(self):
        """Test create_node_stats_aggregator creates instance."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        agg = factory.create_node_stats_aggregator()
        assert agg is not None

    def test_create_node_stats_aggregator_singleton(self):
        """Test create_node_stats_aggregator returns same instance."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        agg1 = factory.create_node_stats_aggregator()
        agg2 = factory.create_node_stats_aggregator()
        assert agg1 is agg2

    def test_create_job_run_manager(self):
        """Test create_job_run_manager creates DefaultJobRunManager."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY, framework_type=FrameworkType.DEFAULT)
        manager = factory.create_job_run_manager()
        assert manager is not None

    def test_create_job_run_manager_singleton(self):
        """Test create_job_run_manager returns same instance."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        mgr1 = factory.create_job_run_manager()
        mgr2 = factory.create_job_run_manager()
        assert mgr1 is mgr2

    def test_create_job_management_service(self):
        """Test create_job_management_service creates instance."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        svc = factory.create_job_management_service()
        assert svc is not None

    def test_create_job_management_service_singleton(self):
        """Test create_job_management_service returns same instance."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        svc1 = factory.create_job_management_service()
        svc2 = factory.create_job_management_service()
        assert svc1 is svc2

    def test_from_environment_invalid_framework_raises(self):
        """Test invalid framework type raises ValueError."""
        with patch.dict(os.environ, {"DOCPIPE_FRAMEWORK_TYPE": "invalid_framework"}):
            with pytest.raises(ValueError, match="Invalid DOCPIPE_FRAMEWORK_TYPE"):
                JobManagementFactory.from_environment()

    def test_resolve_worker_env_in_memory(self):
        """Test resolve_worker_env for in-memory backend."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        env = factory.resolve_worker_env()
        assert "DOCPIPE_STORAGE_BACKEND" in env
        assert env["DOCPIPE_STORAGE_BACKEND"] == StorageBackend.IN_MEMORY.value

    def test_resolve_worker_env_filesystem_with_base_dir(self, tmp_path):
        """Test resolve_worker_env for filesystem backend with base_dir configured."""
        from docpipe.core.job_management.adapters.config.job_management_factory import DocpipeConfigKeys

        config = {DocpipeConfigKeys.BASE_DIR: str(tmp_path)}
        factory = JobManagementFactory(storage_backend=StorageBackend.FILESYSTEM, config=config)
        env = factory.resolve_worker_env()
        assert env["DOCPIPE_STORAGE_BACKEND"] == StorageBackend.FILESYSTEM.value

    def test_resolve_worker_env_postgresql(self):
        """Test resolve_worker_env for postgresql backend."""
        from docpipe.core.job_management.adapters.config.job_management_factory import DocpipeConfigKeys

        config = {
            DocpipeConfigKeys.POSTGRES: {
                "host": "localhost",
                "port": 5432,
                "database": "testdb",
                "user": "user",
                "password": os.environ.get("TEST_DB_PASSWORD", "test-db-pw"),
            }
        }
        factory = JobManagementFactory(storage_backend=StorageBackend.POSTGRESQL, config=config)
        env = factory.resolve_worker_env()
        assert env["DOCPIPE_STORAGE_BACKEND"] == StorageBackend.POSTGRESQL.value

    def test_from_config_file_not_found_raises(self):
        """Test from_config_file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            JobManagementFactory.from_config_file("/nonexistent/path/config.yaml")

    def test_from_config_file_invalid_yaml_raises(self, tmp_path):
        """Test from_config_file raises ValueError on invalid YAML."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [unclosed")

        with pytest.raises(ValueError, match="Invalid YAML"):
            JobManagementFactory.from_config_file(str(bad_yaml))

    def test_from_config_file_empty_yaml_returns_defaults(self, tmp_path):
        """Test from_config_file with empty YAML returns default factory."""
        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("")

        factory = JobManagementFactory.from_config_file(str(empty_yaml))
        assert factory.storage_backend == StorageBackend.IN_MEMORY

    def test_from_config_file_valid_yaml(self, tmp_path):
        """Test from_config_file with valid YAML."""
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text("""
job_management:
  store:
    type: inmemory
  framework:
    type: default
""")
        factory = JobManagementFactory.from_config_file(str(config_yaml))
        assert factory.storage_backend == StorageBackend.IN_MEMORY

    def test_from_config_file_invalid_storage_backend_raises(self, tmp_path):
        """Test from_config_file raises ValueError for invalid backend."""
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text("""
job_management:
  store:
    type: invalid_backend
""")
        with pytest.raises(ValueError, match="Invalid storage backend"):
            JobManagementFactory.from_config_file(str(config_yaml))

    def test_from_default_sources_no_config_file(self, tmp_path):
        """Test from_default_sources when config file doesn't exist."""
        with patch.dict(os.environ, {"DOCPIPE_CONFIG_PATH": str(tmp_path / "nonexistent.yaml")}, clear=False):
            with patch.dict(os.environ, {}, clear=False):
                factory = JobManagementFactory.from_default_sources()
                assert factory is not None

    def test_initialize_storage_skipped_for_non_postgresql(self):
        """Test initialize_storage is no-op for non-postgresql backends."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        factory.initialize_storage()  # Should not raise
        # No assertions needed - just verifying no exception

    def test_initialize_storage_skipped_when_already_initialized(self):
        """Test initialize_storage skips if already initialized."""
        from docpipe.core.job_management.adapters.config.job_management_factory import DocpipeConfigKeys

        factory = JobManagementFactory(
            storage_backend=StorageBackend.POSTGRESQL,
            config={DocpipeConfigKeys.STORAGE_INITIALIZED: True},
        )
        factory.initialize_storage()  # Should not call run_migrations

    def test_get_default_factory_singleton(self):
        """Test get_default_factory returns singleton instance."""
        from docpipe.core.job_management.adapters.config.job_management_factory import (
            get_default_factory,
            reset_default_factory,
        )

        reset_default_factory()
        factory1 = get_default_factory()
        factory2 = get_default_factory()
        assert factory1 is factory2
        reset_default_factory()

    def test_reset_default_factory(self):
        """Test reset_default_factory clears singleton."""
        from docpipe.core.job_management.adapters.config.job_management_factory import (
            get_default_factory,
            reset_default_factory,
        )

        reset_default_factory()
        factory1 = get_default_factory()
        reset_default_factory()
        factory2 = get_default_factory()
        assert factory1 is not factory2
        reset_default_factory()
