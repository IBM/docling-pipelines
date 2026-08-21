"""
Tests for PostgreSQL Alembic migrations.

These tests validate the migration setup, configuration, and execution.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.job_management.adapters.stores.postgres.database import (
    run_migrations,
)
from docpipe.exceptions.docpipe_exceptions import DatabaseMigrationException


class TestMigrationSetup:
    """Test Alembic migration setup and configuration."""

    @pytest.fixture
    def migrations_dir(self):
        """Get migrations directory path."""
        # Navigate from tests/unit/core/job_management/adapters/stores/postgres/test_migrations.py
        # to src/docpipe/core/job_management/adapters/stores/postgres/migrations
        test_file = Path(__file__)
        repo_root = test_file.parents[7]  # Get to repo root
        backend_dir = repo_root / "src" / "docpipe"
        return backend_dir / "core" / "job_management" / "adapters" / "stores" / "postgres" / "migrations"

    def test_migrations_directory_exists(self, *, migrations_dir):
        """Test that migrations directory exists."""
        assert migrations_dir.exists(), f"Migrations directory not found: {migrations_dir}"
        assert migrations_dir.is_dir(), f"Migrations path is not a directory: {migrations_dir}"

    def test_alembic_ini_exists(self, *, migrations_dir):
        """Test that alembic.ini exists."""
        alembic_ini = migrations_dir / "alembic.ini"
        assert alembic_ini.exists(), f"alembic.ini not found: {alembic_ini}"
        assert alembic_ini.is_file(), f"alembic.ini is not a file: {alembic_ini}"

    def test_env_py_exists(self, *, migrations_dir):
        """Test that env.py exists."""
        env_py = migrations_dir / "env.py"
        assert env_py.exists(), f"env.py not found: {env_py}"
        assert env_py.is_file(), f"env.py is not a file: {env_py}"

    def test_script_mako_exists(self, *, migrations_dir):
        """Test that script.py.mako template exists."""
        script_mako = migrations_dir / "script.py.mako"
        assert script_mako.exists(), f"script.py.mako not found: {script_mako}"
        assert script_mako.is_file(), f"script.py.mako is not a file: {script_mako}"

    def test_versions_directory_exists(self, *, migrations_dir):
        """Test that versions directory exists."""
        versions_dir = migrations_dir / "versions"
        assert versions_dir.exists(), f"Versions directory not found: {versions_dir}"
        assert versions_dir.is_dir(), f"Versions path is not a directory: {versions_dir}"

    def test_initial_migration_exists(self, *, migrations_dir):
        """Test that initial migration file exists."""
        versions_dir = migrations_dir / "versions"
        migration_files = list(versions_dir.glob("*_initial_schema.py"))
        assert len(migration_files) > 0, f"No initial migration found in {versions_dir}"
        assert migration_files[0].is_file(), f"Initial migration is not a file: {migration_files[0]}"

    def test_alembic_ini_content(self, *, migrations_dir):
        """Test that alembic.ini has required configuration."""
        alembic_ini = migrations_dir / "alembic.ini"
        content = alembic_ini.read_text()

        # Check for required sections
        assert "[alembic]" in content, "Missing [alembic] section in alembic.ini"
        assert "script_location" in content, "Missing script_location in alembic.ini"
        assert "sqlalchemy.url" in content, "Missing sqlalchemy.url in alembic.ini"

    def test_env_py_imports(self, *, migrations_dir):
        """Test that env.py has required imports."""
        env_py = migrations_dir / "env.py"
        content = env_py.read_text()

        # Check for required imports
        assert "from alembic import context" in content, "Missing alembic context import"
        assert "from sqlalchemy import" in content, "Missing sqlalchemy import"
        assert "from sqlmodel import SQLModel" in content, "Missing SQLModel import"
        assert "from docpipe.core.job_management.adapters.stores.postgres.models import" in content, (
            "Missing models import"
        )

    def test_initial_migration_structure(self, *, migrations_dir):
        """Test that initial migration has required structure."""
        versions_dir = migrations_dir / "versions"
        migration_files = list(versions_dir.glob("*_initial_schema.py"))
        assert len(migration_files) > 0, "No initial migration found"

        content = migration_files[0].read_text()

        # Check for required elements
        assert "revision:" in content, "Missing revision identifier"
        assert "down_revision:" in content, "Missing down_revision identifier"
        assert "def upgrade()" in content, "Missing upgrade function"
        assert "def downgrade()" in content, "Missing downgrade function"
        assert "job_run_stats" in content, "Missing job_run_stats table"
        assert "node_stats" in content, "Missing node_stats table"

    def test_initial_migration_node_stats_indexes(self, *, migrations_dir):
        """Test that initial migration includes required node_stats indexes."""
        versions_dir = migrations_dir / "versions"
        migration_files = list(versions_dir.glob("*_initial_schema.py"))
        assert len(migration_files) > 0, "No initial migration found"

        content = migration_files[0].read_text()

        # Check for partial unique index on (node_id, job_run_id, batch_id) where batch_id IS NOT NULL
        assert "ix_docpipe_node_stats_node_job_batch" in content, (
            "Missing partial unique index on (node_id, job_run_id, batch_id) where batch_id IS NOT NULL"
        )
        assert "batch_id IS NOT NULL" in content, (
            "Missing WHERE clause for batch_id IS NOT NULL in partial unique index"
        )

        # Check for partial unique index on (node_id, job_run_id) where batch_id IS NULL
        assert "ix_docpipe_node_stats_node_job_no_batch" in content, (
            "Missing partial unique index on (node_id, job_run_id) where batch_id IS NULL"
        )
        assert "batch_id IS NULL" in content, "Missing WHERE clause for batch_id IS NULL in partial unique index"

        # Check for non-unique index on job_run_id
        assert "ix_docpipe_node_stats_job_run_id" in content, "Missing non-unique index on job_run_id"

        # Verify index creation calls with proper parameters
        assert '"node_id", "job_run_id", "batch_id"' in content, "Missing columns for batch index"
        assert '"node_id", "job_run_id"' in content, "Missing columns for no-batch index"
        assert '["job_run_id"]' in content, "Missing column for job_run_id index"

    def test_initial_migration_downgrade_drops_indexes(self, *, migrations_dir):
        """Test that downgrade function properly drops node_stats indexes."""
        versions_dir = migrations_dir / "versions"
        migration_files = list(versions_dir.glob("*_initial_schema.py"))
        assert len(migration_files) > 0, "No initial migration found"

        content = migration_files[0].read_text()

        # Extract downgrade function
        downgrade_start = content.find("def downgrade()")
        assert downgrade_start != -1, "Missing downgrade function"
        downgrade_content = content[downgrade_start:]

        # Check that all three indexes are dropped in downgrade
        assert 'drop_index("ix_docpipe_node_stats_job_run_id"' in downgrade_content, (
            "Downgrade missing drop for ix_docpipe_node_stats_job_run_id"
        )
        assert 'drop_index("ix_docpipe_node_stats_node_job_no_batch"' in downgrade_content, (
            "Downgrade missing drop for ix_docpipe_node_stats_node_job_no_batch"
        )
        assert 'drop_index("ix_docpipe_node_stats_node_job_batch"' in downgrade_content, (
            "Downgrade missing drop for ix_docpipe_node_stats_node_job_batch"
        )

    def test_migration_revision_format(self, *, migrations_dir):
        """Test that migration revision follows expected format."""
        versions_dir = migrations_dir / "versions"
        migration_files = list(versions_dir.glob("*_initial_schema.py"))
        assert len(migration_files) > 0, "No initial migration found"

        content = migration_files[0].read_text()

        # Extract revision line
        for line in content.split("\n"):
            if line.strip().startswith("revision:"):
                # Should be in format: revision: str = '20260422_001'
                assert "'" in line or '"' in line, "Revision should be a string"
                break
        else:
            pytest.fail("Could not find revision line in migration")


class TestMigrationExecution:
    """Test migration execution functionality."""

    @pytest.fixture
    def mock_connection_string(self):
        """Provide a mock connection string."""
        return "postgresql+psycopg2://user:pass@localhost:5432/testdb"  # pragma: allowlist secret

    def test_run_migrations_missing_alembic_ini(self, *, mock_connection_string):
        """Test that run_migrations raises error when alembic.ini is missing."""
        with patch("docpipe.core.job_management.adapters.stores.postgres.database.ALEMBIC_INI_PATH") as mock_path:
            mock_path.exists.return_value = False
            mock_path.__str__.return_value = "/fake/path/alembic.ini"  # type: ignore[attr-defined]

            with pytest.raises(DatabaseMigrationException) as exc_info:
                run_migrations(connection_string=mock_connection_string)

            assert "Alembic configuration not found" in str(exc_info.value)
            assert exc_info.value.operation == "verify_config"

    @patch("docpipe.core.job_management.adapters.stores.postgres.database.command")
    @patch("docpipe.core.job_management.adapters.stores.postgres.database.AlembicConfig")
    def test_run_migrations_success(self, mock_alembic_config, mock_command, *, mock_connection_string):
        """Test successful migration execution."""
        # Setup mocks
        mock_cfg = MagicMock()
        mock_alembic_config.return_value = mock_cfg

        # Execute
        run_migrations(connection_string=mock_connection_string)

        # Verify
        mock_alembic_config.assert_called_once()
        mock_cfg.set_main_option.assert_any_call("sqlalchemy.url", mock_connection_string)
        mock_command.upgrade.assert_called_once_with(mock_cfg, "head")

    @patch("docpipe.core.job_management.adapters.stores.postgres.database.command")
    @patch("docpipe.core.job_management.adapters.stores.postgres.database.AlembicConfig")
    def test_run_migrations_with_config(self, mock_alembic_config, mock_command, *, mock_connection_string):
        """Test migration execution with additional config."""
        mock_cfg = MagicMock()
        mock_alembic_config.return_value = mock_cfg

        config = {"some_key": "some_value"}
        run_migrations(connection_string=mock_connection_string, config=config)

        # Should still work with config dict
        mock_command.upgrade.assert_called_once_with(mock_cfg, "head")

    @patch("docpipe.core.job_management.adapters.stores.postgres.database.command")
    @patch("docpipe.core.job_management.adapters.stores.postgres.database.AlembicConfig")
    def test_run_migrations_alembic_failure(self, mock_alembic_config, mock_command, *, mock_connection_string):
        """Test migration execution when Alembic command fails."""
        mock_cfg = MagicMock()
        mock_alembic_config.return_value = mock_cfg
        mock_command.upgrade.side_effect = Exception("Alembic upgrade failed")

        with pytest.raises(DatabaseMigrationException) as exc_info:
            run_migrations(connection_string=mock_connection_string)

        assert "Database migration failed" in str(exc_info.value)
        assert exc_info.value.operation == "upgrade"

    @patch("docpipe.core.job_management.adapters.stores.postgres.database.command")
    @patch("docpipe.core.job_management.adapters.stores.postgres.database.AlembicConfig")
    def test_run_migrations_sets_script_location(self, mock_alembic_config, mock_command, *, mock_connection_string):
        """Test that run_migrations sets the script location correctly."""
        mock_cfg = MagicMock()
        mock_alembic_config.return_value = mock_cfg

        run_migrations(connection_string=mock_connection_string)

        # Verify script_location was set
        calls = mock_cfg.set_main_option.call_args_list
        script_location_calls = [call for call in calls if call[0][0] == "script_location"]
        assert len(script_location_calls) == 1, "script_location should be set once"
