"""Tests for FilesystemDestinationAdapter."""

from unittest.mock import patch

from docpipe.core.operators.storage.adapters.outbound.destinations.filesystem.adapter import (
    FilesystemDestinationAdapter,
)
from docpipe.core.operators.storage.adapters.outbound.destinations.filesystem.config import (
    FilesystemDestinationConfig,
)


class TestFilesystemDestinationAdapterWriteDocument:
    def test_writes_file_and_returns_success(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        dest = str(tmp_path / "out.md")
        content = b"# Hello World"

        result = adapter.write_document(content=content, destination_path=dest, overwrite=True)

        assert result.success is True
        assert result.write_status == "success"
        assert result.bytes_written == len(content)
        assert result.destination_path == dest
        assert (tmp_path / "out.md").read_bytes() == content

    def test_creates_nested_directories(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        dest = str(tmp_path / "a" / "b" / "c" / "out.txt")

        result = adapter.write_document(content=b"nested", destination_path=dest, overwrite=True)

        assert result.success is True
        assert (tmp_path / "a" / "b" / "c" / "out.txt").exists()

    def test_skips_existing_file_when_overwrite_false(self, tmp_path):
        existing = tmp_path / "existing.md"
        existing.write_bytes(b"original")
        adapter = FilesystemDestinationAdapter()

        result = adapter.write_document(
            content=b"new content",
            destination_path=str(existing),
            overwrite=False,
        )

        assert result.success is False
        assert result.write_status == "skipped"
        assert existing.read_bytes() == b"original"  # unchanged

    def test_overwrites_existing_file_when_overwrite_true(self, tmp_path):
        existing = tmp_path / "existing.md"
        existing.write_bytes(b"original")
        adapter = FilesystemDestinationAdapter()

        result = adapter.write_document(
            content=b"replaced",
            destination_path=str(existing),
            overwrite=True,
        )

        assert result.success is True
        assert existing.read_bytes() == b"replaced"

    def test_returns_failed_result_on_permission_error(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        dest = str(tmp_path / "out.md")

        with patch("pathlib.Path.write_bytes", side_effect=PermissionError("denied")):
            result = adapter.write_document(content=b"data", destination_path=dest, overwrite=True)

        assert result.success is False
        assert result.write_status == "failed"
        assert "denied" in result.error_message

    def test_bytes_written_is_zero_on_failure(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        dest = str(tmp_path / "out.md")

        with patch("pathlib.Path.write_bytes", side_effect=OSError("boom")):
            result = adapter.write_document(content=b"data", destination_path=dest, overwrite=True)

        assert result.bytes_written == 0


class TestFilesystemDestinationAdapterEnsureDirectory:
    def test_creates_directory(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        new_dir = str(tmp_path / "new" / "dir")

        adapter.ensure_directory(path=new_dir)

        assert (tmp_path / "new" / "dir").is_dir()

    def test_does_not_fail_if_directory_exists(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        adapter.ensure_directory(path=str(tmp_path))  # already exists — no error


class TestFilesystemDestinationAdapterBuildConfig:
    def test_build_config_from_operator_params(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        config = adapter.build_config_from_operator_params(
            provider_config={
                "root_path": str(tmp_path),
                "create_dirs": False,
            },
            credentials={},
        )
        assert isinstance(config, FilesystemDestinationConfig)
        assert config.root_path == str(tmp_path)
        assert config.create_dirs is False

    def test_build_config_applies_defaults(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        config = adapter.build_config_from_operator_params(
            provider_config={"root_path": str(tmp_path)},
            credentials={},
        )
        assert config.create_dirs is True


class TestFilesystemDestinationAdapterRegistration:
    def test_dest_name_is_filesystem(self):
        assert FilesystemDestinationAdapter.DEST_NAME == "filesystem"

    def test_is_registered_in_factory(self):
        from docpipe.core.operators.storage.adapters.outbound.destinations.factories.destination_factory import (
            DestinationAdapterFactory,
        )

        assert DestinationAdapterFactory.is_registered("filesystem")


class TestFilesystemDestinationAdapterResolveDestinationPath:
    def test_prepends_root_path(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        config = FilesystemDestinationConfig(root_path=str(tmp_path))
        result = adapter.resolve_destination_path(relative_path="subdir/doc.md", config=config)
        assert result == str(tmp_path / "subdir" / "doc.md")

    def test_flat_relative_path(self, tmp_path):
        adapter = FilesystemDestinationAdapter()
        config = FilesystemDestinationConfig(root_path=str(tmp_path))
        result = adapter.resolve_destination_path(relative_path="doc.md", config=config)
        assert result == str(tmp_path / "doc.md")
