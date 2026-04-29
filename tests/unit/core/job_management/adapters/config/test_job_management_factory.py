"""
Tests for JobManagementFactory configuration and store selection.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from core.job_management.adapters.config import (
    JobManagementFactory,
    StorageBackend,
    FrameworkType,
)


class TestJobManagementFactoryStoreSelection:
    """Test factory store selection logic."""

    def test_inmemory_store_creation(self):
        """Test InMemoryJobStatsStore creation."""
        factory = JobManagementFactory(storage_backend=StorageBackend.IN_MEMORY)
        store = factory.create_job_stats_store()

        assert store is not None
        assert store.__class__.__name__ == "InMemoryJobStatsStore"

    def test_json_store_creation(self):
        """Test JsonJobStatsStore creation."""
        factory = JobManagementFactory(storage_backend=StorageBackend.JSON)
        store = factory.create_job_stats_store()

        assert store is not None
        assert store.__class__.__name__ == "JsonJobStatsStore"

    @patch("core.job_management.adapters.config.job_management_factory.run_migrations")
    @patch(
        "core.job_management.adapters.stores.postgres.postgres_job_stats_store.create_session_factory"
    )
    @patch(
        "core.job_management.adapters.stores.postgres.postgres_job_stats_store.create_postgres_engine"
    )
    @patch(
        "core.job_management.adapters.stores.postgres.postgres_job_stats_store.get_postgres_connection_string"
    )
    def test_postgresql_store_creation_with_config(
        self, mock_conn_string, mock_engine, mock_session_factory, mock_run_migrations
    ):
        """Test PostgresJobStatsStore creation with config."""
        # Mock successful PostgreSQL setup
        mock_conn_string.return_value = "postgresql+psycopg2://user:pass@localhost:5432/datasift"  # pragma: allowlist secret
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_session_factory.return_value = MagicMock()

        config = {
            "postgres": {
                "host": "localhost",
                "port": 5432,
                "database": "datasift",
                "user": "test_user",
                "password": "test_password",  # pragma: allowlist secret
            }
        }

        factory = JobManagementFactory(
            storage_backend=StorageBackend.POSTGRESQL, config=config
        )
        store = factory.create_job_stats_store()

        assert store is not None
        assert store.__class__.__name__ == "PostgresJobStatsStore"
        mock_conn_string.assert_called_once_with(config=config)
        mock_engine.assert_called_once()
        mock_session_factory.assert_called_once_with(engine=mock_engine_instance)

    def test_postgresql_store_creation_without_password_raises_error(self):
        """Test PostgresJobStatsStore creation fails without password."""
        factory = JobManagementFactory(storage_backend=StorageBackend.POSTGRESQL)

        from common.exceptions.datasift_exceptions import (
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
                "DATASIFT_STORAGE_BACKEND": "postgresql",
                "DATASIFT_FRAMEWORK_TYPE": "default",
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
        with patch.dict(os.environ, {"DATASIFT_STORAGE_BACKEND": "invalid_backend"}):
            with pytest.raises(ValueError, match="Invalid DATASIFT_STORAGE_BACKEND"):
                JobManagementFactory.from_environment()


# Made with Bob
