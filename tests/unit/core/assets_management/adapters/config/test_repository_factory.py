"""Tests for RepositoryFactory.

This test module verifies the repository factory behavior with different
environment variable configurations.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from common.exceptions.datasift_exceptions import RepositoryConfigurationException
from core.assets_management.adapters.config.repository_factory import (
    RepositoryFactory,
    RepositoryType,
)
from core.assets_management.adapters.repositories.local.local_flow_repository import (
    LocalFlowRepository,
)
from core.assets_management.domain.ports.flow_repository import FlowRepository


class TestRepositoryFactory:
    """Test suite for RepositoryFactory."""

    def test_create_default_flow_repository_returns_local_repository(self):
        """Test that create_default_flow_repository returns LocalFlowRepository."""
        repository = RepositoryFactory.create_default_flow_repository()

        assert isinstance(repository, LocalFlowRepository)
        assert isinstance(repository, FlowRepository)

    def test_create_flow_repository_with_no_env_var_uses_default(self):
        """Test that when FLOW_REPOSITORY_TYPE is not set, it defaults to LOCAL."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove FLOW_REPOSITORY_TYPE if it exists
            os.environ.pop("FLOW_REPOSITORY_TYPE", None)

            repository = RepositoryFactory.create_flow_repository()

            assert isinstance(repository, LocalFlowRepository)
            assert isinstance(repository, FlowRepository)

    def test_create_flow_repository_with_local_env_var(self):
        """Test that FLOW_REPOSITORY_TYPE=local creates LocalFlowRepository."""
        with patch.dict(os.environ, {"FLOW_REPOSITORY_TYPE": "local"}):
            repository = RepositoryFactory.create_flow_repository()

            assert isinstance(repository, LocalFlowRepository)
            assert isinstance(repository, FlowRepository)

    def test_create_flow_repository_with_invalid_env_var_raises_error(self):
        """Test that invalid FLOW_REPOSITORY_TYPE raises RepositoryConfigurationException."""
        with patch.dict(os.environ, {"FLOW_REPOSITORY_TYPE": "invalid_type"}):
            with pytest.raises(RepositoryConfigurationException) as exc_info:
                RepositoryFactory.create_flow_repository()

            error = exc_info.value
            error_msg = str(error)
            assert "Invalid repository type" in error_msg
            assert "invalid_type" in error_msg
            assert "local" in error_msg
            assert error.repository_type == "invalid_type"
            assert error.valid_types == ["local"]

    def test_create_flow_repository_with_default_env_fallback(self):
        """Test that create_flow_repository defaults to local when env var is unset."""
        with patch.dict(os.environ, {}, clear=True):
            repository = RepositoryFactory.create_flow_repository()

            assert isinstance(repository, LocalFlowRepository)

    def test_create_flow_repository_with_custom_flows_dir(self, monkeypatch):
        """Test that LocalFlowRepository can be created with custom flows_dir via environment."""
        custom_dir = Path("/tmp/test_flows")

        # Set environment variable and create repository
        monkeypatch.setenv("LOCAL_FLOWS_DIR", str(custom_dir))
        repository = LocalFlowRepository()

        assert isinstance(repository, LocalFlowRepository)
        # The repository should have the custom directory set
        assert repository.flows_dir == custom_dir

    def test_create_flow_repository_with_flows_dir_as_string(self, monkeypatch):
        """Test that LocalFlowRepository accepts flows_dir as string via environment."""
        custom_dir_str = "/tmp/test_flows_string"

        # Set environment variable and create repository
        monkeypatch.setenv("LOCAL_FLOWS_DIR", custom_dir_str)
        repository = LocalFlowRepository()

        assert isinstance(repository, LocalFlowRepository)
        assert isinstance(repository.flows_dir, Path)
        assert str(repository.flows_dir) == custom_dir_str

    def test_env_var_is_case_insensitive(self):
        """Test that FLOW_REPOSITORY_TYPE is case-insensitive."""
        test_cases = ["local", "LOCAL", "Local", "LoCAl"]

        for repo_type in test_cases:
            with patch.dict(os.environ, {"FLOW_REPOSITORY_TYPE": repo_type}):
                repository = RepositoryFactory.create_flow_repository()
                assert isinstance(repository, LocalFlowRepository)

    def test_invalid_env_var_is_not_overridable(self):
        """Test that invalid env configuration raises an error without programmatic override."""
        with patch.dict(os.environ, {"FLOW_REPOSITORY_TYPE": "invalid"}):
            with pytest.raises(RepositoryConfigurationException) as exc_info:
                RepositoryFactory.create_flow_repository()

            error = exc_info.value
            assert error.repository_type == "invalid"
            assert error.valid_types == ["local"]

    def test_repository_type_enum_values(self):
        """Test that RepositoryType enum has expected values."""
        assert RepositoryType.LOCAL.value == "local"
        # Verify only expected types exist
        assert len(list(RepositoryType)) == 1
