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


class TestBoxSourceConfigFolderIdEnvVar:
    """Test folder_id environment variable expansion in BoxSourceConfig."""

    def test_folder_id_env_var_expanded(self, monkeypatch):
        """folder_id containing ${VAR} is resolved at config creation time."""
        monkeypatch.setenv("BOX_SOURCE_FOLDER_ID", "400527909052")
        config = BoxSourceConfig(
            credentials_path="/tmp/box_config.json",
            folder_id="${BOX_SOURCE_FOLDER_ID}",
        )
        assert config.folder_id == "400527909052"

    def test_folder_id_literal_value_unchanged(self):
        """A plain numeric folder_id is kept as-is."""
        config = BoxSourceConfig(
            credentials_path="/tmp/box_config.json",
            folder_id="12345678",
        )
        assert config.folder_id == "12345678"

    def test_folder_id_unset_env_var_left_as_literal(self, monkeypatch):
        """If the referenced env var is not set, expandvars returns the literal string."""
        monkeypatch.delenv("BOX_MISSING_VAR", raising=False)
        config = BoxSourceConfig(
            credentials_path="/tmp/box_config.json",
            folder_id="${BOX_MISSING_VAR}",
        )
        # os.path.expandvars leaves unresolved vars as-is
        assert "${BOX_MISSING_VAR}" in config.folder_id


class TestBoxSourceAdapterComputeRelativePath:
    """Test BoxSourceAdapter._compute_relative_path."""

    def _make_path_collection(self, entries):
        """Build a simple namespace to mimic Box path_collection."""
        import types

        return types.SimpleNamespace(entries=entries)

    def _make_entry(self, entry_id, name):
        import types

        return types.SimpleNamespace(id=entry_id, name=name)

    def _make_file_info(self, *, name, path_entries):
        import types

        return types.SimpleNamespace(
            name=name,
            path_collection=self._make_path_collection(path_entries),
        )

    def test_single_level_subfolder(self):
        """File inside one sub-folder below the root is returned with subfolder prefix."""
        root_folder_id = "400527909052"
        path_entries = [
            self._make_entry("0", "All Files"),
            self._make_entry("11111", "vt_workspace"),
            self._make_entry(root_folder_id, "source_files"),
            self._make_entry("99999", "sub01"),
        ]
        file_info = self._make_file_info(name="TR-INV_001.pdf", path_entries=path_entries)

        result = BoxSourceAdapter()._compute_relative_path(file_info=file_info, root_folder_id=root_folder_id)
        assert result == "sub01/TR-INV_001.pdf"

    def test_file_at_root_folder(self):
        """File directly inside the root folder has no sub-folder prefix."""
        adapter = BoxSourceAdapter()
        root_folder_id = "400527909052"
        path_entries = [
            self._make_entry("0", "All Files"),
            self._make_entry(root_folder_id, "source_files"),
        ]
        file_info = self._make_file_info(name="direct.pdf", path_entries=path_entries)

        result = adapter._compute_relative_path(file_info=file_info, root_folder_id=root_folder_id)
        assert result == "direct.pdf"

    def test_nested_two_levels(self):
        """File two levels deep returns both subfolder segments."""
        adapter = BoxSourceAdapter()
        root_folder_id = "root_id"
        path_entries = [
            self._make_entry("0", "All Files"),
            self._make_entry(root_folder_id, "root"),
            self._make_entry("level1", "sub01"),
            self._make_entry("level2", "sub02"),
        ]
        file_info = self._make_file_info(name="deep.pdf", path_entries=path_entries)

        result = adapter._compute_relative_path(file_info=file_info, root_folder_id=root_folder_id)
        assert result == "sub01/sub02/deep.pdf"

    def test_root_folder_id_not_in_ancestry_returns_none(self):
        """When root_folder_id is absent from path_collection, None is returned."""
        adapter = BoxSourceAdapter()
        path_entries = [
            self._make_entry("0", "All Files"),
            self._make_entry("other_id", "other_folder"),
        ]
        file_info = self._make_file_info(name="orphan.pdf", path_entries=path_entries)

        result = adapter._compute_relative_path(file_info=file_info, root_folder_id="missing_root")
        assert result is None

    def test_missing_path_collection_returns_none(self):
        """file_info with no path_collection attribute returns None."""
        import types

        adapter = BoxSourceAdapter()
        file_info = types.SimpleNamespace(name="test.pdf", path_collection=None)
        result = adapter._compute_relative_path(file_info=file_info, root_folder_id="any_id")
        assert result is None

    def test_empty_filename_returns_none(self):
        """file_info with an empty name returns None."""
        adapter = BoxSourceAdapter()
        root_folder_id = "root_id"
        path_entries = [self._make_entry(root_folder_id, "root")]
        file_info = self._make_file_info(name="", path_entries=path_entries)

        result = adapter._compute_relative_path(file_info=file_info, root_folder_id=root_folder_id)
        assert result is None
