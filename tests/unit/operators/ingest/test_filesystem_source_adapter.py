#!/usr/bin/env python3

import asyncio
import os
from unittest.mock import mock_open, patch

import pytest
from pydantic import ValidationError

from docpipe.core.operators.ingest.adapters.outbound.sources.filesystem.adapter import (
    FilesystemSourceAdapter,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.filesystem.config import (
    FilesystemSourceConfig,
)


async def collect_async(async_gen):
    return [item async for item in async_gen]


class TestFilesystemSourceConfig:
    def test_expands_root_path(self, tmp_path):
        config = FilesystemSourceConfig(
            root_path=str(tmp_path),
            recursive=True,
            max_file_size_mb=None,
            follow_symlinks=False,
        )
        assert config.root_path == str(tmp_path)

    def test_rejects_missing_root_path(self):
        with pytest.raises(ValidationError, match="Root path does not exist"):
            FilesystemSourceConfig(
                root_path="/definitely/missing/path",
                recursive=True,
                max_file_size_mb=None,
                follow_symlinks=False,
            )

    def test_rejects_non_directory(self, tmp_path):
        file_path = tmp_path / "file.txt"
        file_path.write_text("x")

        with pytest.raises(ValidationError, match="Root path is not a directory"):
            FilesystemSourceConfig(
                root_path=str(file_path),
                recursive=True,
                max_file_size_mb=None,
                follow_symlinks=False,
            )

    def test_normalizes_extensions_and_validates_size(self, tmp_path):
        config = FilesystemSourceConfig(
            root_path=str(tmp_path),
            recursive=True,
            file_extensions=["txt", ".pdf"],
            max_file_size_mb=5,
            follow_symlinks=False,
        )
        assert config.file_extensions == [".txt", ".pdf"]
        assert config.max_file_size_mb == 5

    def test_rejects_non_positive_max_file_size(self, tmp_path):
        with pytest.raises(ValidationError, match="max_file_size_mb must be positive"):
            FilesystemSourceConfig(
                root_path=str(tmp_path),
                recursive=True,
                max_file_size_mb=0,
                follow_symlinks=False,
            )


class TestFilesystemSourceAdapter:
    def test_build_config_from_operator_params(self, tmp_path):
        adapter = FilesystemSourceAdapter()
        config = adapter.build_config_from_operator_params(
            connection_params={
                "root_path": str(tmp_path),
                "recursive": False,
                "exclude_patterns": ["*.tmp"],
                "follow_symlinks": True,
                "max_file_size_mb": 3,
            },
            credentials={},
            included_extensions=["txt"],
        )
        config_data = config.model_dump()

        assert type(config).__name__ == "FilesystemSourceConfig"
        assert config_data["root_path"] == str(tmp_path)
        assert config_data["recursive"] is False
        assert config_data["file_extensions"] == [".txt"]
        assert config_data["exclude_patterns"] == ["*.tmp"]
        assert config_data["follow_symlinks"] is True
        assert config_data["max_file_size_mb"] == 3

    def test_walk_directory_non_recursive_and_filters(self, tmp_path):
        included = tmp_path / "keep.txt"
        included.write_text("hello")
        excluded = tmp_path / "skip.tmp"
        excluded.write_text("tmp")
        nested_dir = tmp_path / "nested"
        nested_dir.mkdir()
        (nested_dir / "nested.txt").write_text("nested")

        config = FilesystemSourceConfig(
            root_path=str(tmp_path),
            recursive=False,
            file_extensions=[".txt"],
            exclude_patterns=["*.tmp"],
            max_file_size_mb=None,
            follow_symlinks=False,
        )
        adapter = FilesystemSourceAdapter()

        result = list(adapter._walk_directory(tmp_path, config))
        assert result == [included]

    def test_should_include_file_and_exclusion(self, tmp_path):
        adapter = FilesystemSourceAdapter()
        config = FilesystemSourceConfig(
            root_path=str(tmp_path),
            recursive=True,
            file_extensions=[".txt"],
            exclude_patterns=["*ignore*"],
            max_file_size_mb=None,
            follow_symlinks=False,
        )

        assert adapter._should_include_file(tmp_path / "ok.txt", config) is True
        assert adapter._should_include_file(tmp_path / "ok.pdf", config) is False
        assert adapter._should_include_file(tmp_path / "ignore.txt", config) is False
        assert adapter._is_excluded(str(tmp_path / "ignore.txt"), config) is True
        assert adapter._is_excluded(str(tmp_path / "ok.txt"), config) is False

    def test_fetch_documents_skips_large_files_and_handles_read_errors(self, tmp_path):
        small = tmp_path / "small.txt"
        small.write_text("hello")
        large = tmp_path / "large.txt"
        large.write_text("x" * 10)

        config = FilesystemSourceConfig(
            root_path=str(tmp_path),
            recursive=False,
            file_extensions=[".txt"],
            max_file_size_mb=1,
            follow_symlinks=False,
        )
        adapter = FilesystemSourceAdapter()

        large_stat = large.stat()

        def fake_open(path, mode="rb", *args, **kwargs):
            if str(path).endswith("small.txt"):
                raise OSError("boom")
            return mock_open(read_data=b"x")()

        with (
            patch.object(
                FilesystemSourceAdapter,
                "_walk_directory",
                return_value=iter([small, large]),
            ),
            patch(
                "builtins.open",
                side_effect=fake_open,
            ),
            patch(
                "pathlib.Path.stat",
                return_value=os.stat_result(
                    (
                        large_stat.st_mode,
                        large_stat.st_ino,
                        large_stat.st_dev,
                        large_stat.st_nlink,
                        large_stat.st_uid,
                        large_stat.st_gid,
                        2 * 1024 * 1024,
                        int(large_stat.st_atime),
                        int(large_stat.st_mtime),
                        int(large_stat.st_ctime),
                    )
                ),
            ),
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert docs == []

    def test_fetch_documents_returns_document(self, tmp_path):
        file_path = tmp_path / "doc.txt"
        file_path.write_text("hello world")
        config = FilesystemSourceConfig(
            root_path=str(tmp_path),
            recursive=False,
            max_file_size_mb=None,
            follow_symlinks=False,
        )
        adapter = FilesystemSourceAdapter()

        docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 1
        doc = docs[0]
        assert doc.name == "doc.txt"
        assert doc.content == b"hello world"
        assert doc.extension == ".txt"
        assert doc.metadata["relative_path"] == "doc.txt"

    def test_fetch_binary_content_reads_file_uri(self, tmp_path):
        file_path = tmp_path / "doc with spaces.txt"
        file_path.write_text("hello file uri")

        adapter = FilesystemSourceAdapter()
        content = adapter.fetch_binary_content(
            source_id=file_path.resolve().as_uri(),
            connection_params={"root_path": str(tmp_path)},
            credentials={},
        )

        assert content == b"hello file uri"

    def test_test_connection_variants(self, tmp_path):
        adapter = FilesystemSourceAdapter()
        config = FilesystemSourceConfig(
            root_path=str(tmp_path),
            recursive=True,
            max_file_size_mb=None,
            follow_symlinks=False,
        )

        success, message = asyncio.run(adapter.test_connection(config))
        assert success is True
        assert "Successfully connected" in message

        with patch("pathlib.Path.exists", return_value=False):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "Path does not exist" in message

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=False),
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "Path is not a directory" in message

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("os.access", return_value=False),
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "Path is not readable" in message

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("os.access", return_value=True),
            patch("pathlib.Path.iterdir", side_effect=PermissionError),
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "Permission denied" in message
