"""Tests for FilesystemDestinationConfig."""

import pytest
from pydantic import ValidationError

from docpipe.core.operators.storage.adapters.outbound.destinations.filesystem.config import (
    FilesystemDestinationConfig,
)


class TestFilesystemDestinationConfig:
    def test_valid_existing_directory(self, tmp_path):
        config = FilesystemDestinationConfig(root_path=str(tmp_path))
        assert config.root_path == str(tmp_path)

    def test_valid_nonexistent_path_is_accepted(self, tmp_path):
        """Destination may not exist yet — operator will create it."""
        new_dir = str(tmp_path / "new" / "nested")
        config = FilesystemDestinationConfig(root_path=new_dir)
        assert config.root_path == new_dir

    def test_home_dir_expansion(self):
        config = FilesystemDestinationConfig(root_path="~/some/output")
        assert not config.root_path.startswith("~")

    def test_defaults(self, tmp_path):
        config = FilesystemDestinationConfig(root_path=str(tmp_path))
        assert config.create_dirs is True

    def test_create_dirs_false(self, tmp_path):
        config = FilesystemDestinationConfig(root_path=str(tmp_path), create_dirs=False)
        assert config.create_dirs is False

    def test_missing_root_path_raises(self):
        with pytest.raises(ValidationError):
            FilesystemDestinationConfig()
