#!/usr/bin/env python3

import pytest

from docpipe.core.operators.ingest.adapters.outbound.sources.box.adapter import BoxSourceAdapter
from docpipe.core.operators.ingest.adapters.outbound.sources.box.config import BoxSourceConfig


class TestBoxSourceConfig:
    """Test BoxSourceConfig validation and defaults."""

    def test_default_folder_id_is_root(self):
        """Test that folder_id defaults to '0' (root folder)."""
        config = BoxSourceConfig(
            credentials_path="/tmp/box_config.json",
            recursive=True,
        )
        assert config.folder_id == "0"

    def test_custom_folder_id(self):
        """Test that custom folder_id is accepted."""
        config = BoxSourceConfig(
            credentials_path="/tmp/box_config.json",
            folder_id="123456789",
            recursive=True,
        )
        assert config.folder_id == "123456789"

    def test_expands_credentials_path(self):
        """Test that credentials path is expanded."""
        config = BoxSourceConfig(
            credentials_path="~/box_config.json",
            recursive=True,
        )
        assert config.credentials_path.endswith("box_config.json")
        assert not config.credentials_path.startswith("~")

    def test_normalizes_extensions(self):
        """Test that file extensions are normalized with dots."""
        config = BoxSourceConfig(
            credentials_path="/tmp/box_config.json",
            file_extensions=["pdf", ".docx", "txt"],
        )
        assert config.file_extensions == [".pdf", ".docx", ".txt"]

    def test_validates_max_file_size(self):
        """Test that max_file_size_mb must be positive."""
        with pytest.raises(ValueError, match="max_file_size_mb must be positive"):
            BoxSourceConfig(
                credentials_path="/tmp/box_config.json",
                max_file_size_mb=-1,
            )


class TestBoxSourceAdapter:
    """Test BoxSourceAdapter configuration building."""

    def test_build_config_from_operator_params_with_folder_id(self):
        """Test building config with custom folder_id."""
        adapter = BoxSourceAdapter()
        config = adapter.build_config_from_operator_params(
            connection_params={
                "folder_id": "123456789",
                "recursive": True,
                "max_file_size_mb": 50,
                "exclude_patterns": ["*.tmp"],
            },
            credentials={
                "credentials_json_path": "/tmp/box_config.json",
            },
            included_extensions=["pdf", "docx"],
        )

        assert isinstance(config, BoxSourceConfig)
        assert config.folder_id == "123456789"
        assert config.recursive is True
        assert config.max_file_size_mb == 50
        assert config.exclude_patterns == ["*.tmp"]
        assert config.file_extensions == [".pdf", ".docx"]
        assert config.credentials_path == "/tmp/box_config.json"

    def test_build_config_defaults_to_root_folder(self):
        """Test that folder_id defaults to '0' when not specified."""
        adapter = BoxSourceAdapter()
        config = adapter.build_config_from_operator_params(
            connection_params={
                "recursive": False,
            },
            credentials={
                "credentials_json_path": "/tmp/box_config.json",
            },
        )

        assert config.folder_id == "0"
        assert config.recursive is False

    def test_build_config_with_max_files(self):
        """Test building config with max_files parameter."""
        adapter = BoxSourceAdapter()
        config = adapter.build_config_from_operator_params(
            connection_params={
                "folder_id": "987654321",
            },
            credentials={
                "credentials_json_path": "/tmp/box_config.json",
            },
            max_files=100,
        )

        assert config.folder_id == "987654321"
        assert config.max_files == 100

    def test_get_config_schema(self):
        """Test that get_config_schema returns BoxSourceConfig."""
        adapter = BoxSourceAdapter()
        schema = adapter.get_config_schema()
        assert schema == BoxSourceConfig
