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
                "password": "test_password",  # pragma: allowlist secret
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


class TestJobManagementFactoryInitializeStorage:
    """Tests for initialize_storage() and resolve_worker_env() to boost coverage."""

    def test_initialize_storage_noop_for_non_postgresql(self):
        """initialize_storage does nothing for non-PostgreSQL backends."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        # Should not raise — just returns immediately
        factory.initialize_storage()

    def test_initialize_storage_skips_when_already_initialized(self):
        """initialize_storage skips if STORAGE_INITIALIZED flag is set."""
        factory = JobManagementFactory(
            storage_backend=StorageBackend.POSTGRESQL,
            config={"storage_initialized": True},
        )
        factory.initialize_storage()  # should return without calling run_migrations

    @patch("docpipe.core.job_management.adapters.config.job_management_factory.run_migrations")
    @patch("docpipe.core.job_management.adapters.config.job_management_factory.get_postgres_connection_string")
    def test_initialize_storage_skips_migrations_when_no_connection_string(self, mock_conn_str, mock_migrations):
        """initialize_storage exits early when connection string is empty."""
        mock_conn_str.return_value = ""
        factory = JobManagementFactory(storage_backend=StorageBackend.POSTGRESQL)
        factory.initialize_storage()
        mock_migrations.assert_not_called()

    @patch("docpipe.core.job_management.adapters.config.job_management_factory.run_migrations")
    @patch("docpipe.core.job_management.adapters.config.job_management_factory.get_postgres_connection_string")
    def test_initialize_storage_skips_migrations_when_disabled(self, mock_conn_str, mock_migrations):
        """initialize_storage skips migrations when run_migrations=False."""
        mock_conn_str.return_value = "postgresql://user:pass@localhost/db"  # pragma: allowlist secret
        factory = JobManagementFactory(
            storage_backend=StorageBackend.POSTGRESQL,
            config={"run_migrations": False},
        )
        factory.initialize_storage()
        mock_migrations.assert_not_called()

    def test_resolve_worker_env_includes_backend_and_framework(self):
        """resolve_worker_env always includes storage backend and framework type."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        env = factory.resolve_worker_env()
        assert "DOCPIPE_STORAGE_BACKEND" in env
        assert "DOCPIPE_FRAMEWORK_TYPE" in env

    def test_resolve_worker_env_filesystem_with_env_override(self):
        """resolve_worker_env picks up ENV_JOB_STATS_BASE_DIR_KEY for filesystem backend."""
        factory = JobManagementFactory(storage_backend=StorageBackend.FILESYSTEM)
        with patch.dict(os.environ, {"DOCPIPE_JOB_STATS_BASE_DIR": "/data/jobs"}):
            env = factory.resolve_worker_env()
        assert "DOCPIPE_STORAGE_BACKEND" in env

    def test_resolve_worker_env_postgresql_includes_connection_params(self):
        """resolve_worker_env includes postgres params when configured."""
        config = {
            "postgres": {
                "host": "localhost",
                "port": "5432",
                "database": "docpipe",
                "user": "admin",
                "password": "secret",  # pragma: allowlist secret
            }
        }
        factory = JobManagementFactory(storage_backend=StorageBackend.POSTGRESQL, config=config)
        env = factory.resolve_worker_env()
        assert env.get("DOCPIPE_POSTGRES_HOST") == "localhost"
