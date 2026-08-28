#!/usr/bin/env python3

import asyncio
import os
from unittest.mock import patch

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
    def test_accepts_single_path_in_list(self, tmp_path):
        config = FilesystemSourceConfig(
            paths=[str(tmp_path)],
            recursive=True,
            max_file_size_mb=None,
            follow_symlinks=False,
        )
        assert config.paths == [str(tmp_path)]

    def test_accepts_multiple_paths(self, tmp_path):
        second = tmp_path / "sub"
        second.mkdir()
        config = FilesystemSourceConfig(
            paths=[str(tmp_path), str(second)],
            recursive=True,
            max_file_size_mb=None,
            follow_symlinks=False,
        )
        assert config.paths == [str(tmp_path), str(second)]

    def test_rejects_missing_paths(self):
        with pytest.raises(ValidationError, match="Root path does not exist"):
            FilesystemSourceConfig(
                paths=["/definitely/missing/path"],
                recursive=True,
                max_file_size_mb=None,
                follow_symlinks=False,
            )

    def test_rejects_empty_list(self, tmp_path):
        with pytest.raises(ValidationError, match="at least one path"):
            FilesystemSourceConfig(
                paths=[],
                recursive=True,
                max_file_size_mb=None,
                follow_symlinks=False,
            )

    def test_accepts_file_path(self, tmp_path):
        """Test that config accepts file paths (single file mode)."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test content")

        config = FilesystemSourceConfig(
            paths=[str(file_path)],
            recursive=True,
            max_file_size_mb=None,
            follow_symlinks=False,
        )
        assert config.paths == [str(file_path.resolve())]

    def test_normalizes_extensions_and_validates_size(self, tmp_path):
        config = FilesystemSourceConfig(
            paths=[str(tmp_path)],
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
                paths=[str(tmp_path)],
                recursive=True,
                max_file_size_mb=0,
                follow_symlinks=False,
            )


class TestFilesystemSourceAdapter:
    def test_build_config_from_operator_params(self, tmp_path):
        second = tmp_path / "sub"
        second.mkdir()
        adapter = FilesystemSourceAdapter()
        config = adapter.build_config_from_operator_params(
            connection_params={
                "paths": [str(tmp_path), str(second)],
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
        assert config_data["paths"] == [str(tmp_path), str(second)]
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
            paths=[str(tmp_path)],
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
            paths=[str(tmp_path)],
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

    def test_fetch_documents_skips_large_files(self, tmp_path):
        """Test that large files are skipped in directory mode."""
        small = tmp_path / "small.txt"
        small.write_text("hello")
        large = tmp_path / "large.txt"
        large.write_text("x" * 10)

        config = FilesystemSourceConfig(
            paths=[str(tmp_path)],
            recursive=False,
            file_extensions=[".txt"],
            max_file_size_mb=1,
            follow_symlinks=False,
        )
        adapter = FilesystemSourceAdapter()

        # Store original stat results
        tmp_path_stat = tmp_path.stat()
        large_stat = large.stat()
        small_stat = small.stat()

        def fake_stat(self):
            """Return appropriate stat based on path."""
            path_str = str(self)
            if path_str == str(tmp_path):
                return tmp_path_stat
            if path_str == str(large):
                # Return large file stat (2MB) — should be skipped
                return os.stat_result(
                    (
                        large_stat.st_mode,
                        large_stat.st_ino,
                        large_stat.st_dev,
                        large_stat.st_nlink,
                        large_stat.st_uid,
                        large_stat.st_gid,
                        2 * 1024 * 1024,  # 2MB size
                        int(large_stat.st_atime),
                        int(large_stat.st_mtime),
                        int(large_stat.st_ctime),
                    )
                )
            if path_str == str(small):
                return small_stat
            return type(self).stat(self)

        with (
            patch.object(
                FilesystemSourceAdapter,
                "_walk_directory",
                return_value=iter([small, large]),
            ),
            patch(
                "pathlib.Path.stat",
                fake_stat,
            ),
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        # small.txt yielded (lazy, no read), large.txt skipped due to size limit
        assert len(docs) == 1
        assert docs[0].name == "small.txt"
        assert docs[0].content == b""

    def test_fetch_documents_returns_document(self, tmp_path):
        file_path = tmp_path / "doc.txt"
        file_path.write_text("hello world")
        config = FilesystemSourceConfig(
            paths=[str(tmp_path)],
            recursive=False,
            max_file_size_mb=None,
            follow_symlinks=False,
        )
        adapter = FilesystemSourceAdapter()

        docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 1
        doc = docs[0]
        assert doc.name == "doc.txt"
        assert doc.content == b""  # lazy loading: content empty until fetch_binary_content() called
        assert doc.extension == ".txt"
        assert doc.metadata["relative_path"] == "doc.txt"

    def test_fetch_binary_content_reads_file_uri(self, tmp_path):
        file_path = tmp_path / "doc with spaces.txt"
        file_path.write_text("hello file uri")

        adapter = FilesystemSourceAdapter()
        content = adapter.fetch_binary_content(
            source_id=file_path.resolve().as_uri(),
            connection_params={"paths": [str(tmp_path)]},
            credentials={},
        )

        assert content == b"hello file uri"

    def test_test_connection_variants(self, tmp_path):
        adapter = FilesystemSourceAdapter()
        config = FilesystemSourceConfig(
            paths=[str(tmp_path)],
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
            assert "Path is not a file" in message

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
