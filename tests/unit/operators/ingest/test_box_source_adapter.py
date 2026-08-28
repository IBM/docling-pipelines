#!/usr/bin/env python3

import types
from datetime import UTC, datetime
from unittest.mock import Mock, patch

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(entry_id, name):
    return types.SimpleNamespace(id=entry_id, name=name)


def _make_path_collection(entries):
    return types.SimpleNamespace(entries=entries)


def _make_file_info(
    *, file_id="123", name="test.pdf", size=1024, modified_at=None, created_at=None, path_entries=None, shared_link=None
):
    return types.SimpleNamespace(
        id=file_id,
        name=name,
        size=size,
        modified_at=modified_at,
        created_at=created_at,
        path_collection=_make_path_collection(path_entries or []),
        shared_link=shared_link,
        owned_by=types.SimpleNamespace(login="owner@example.com"),
    )


def _make_config(**kwargs):
    defaults = {"credentials_path": "/tmp/box_config.json"}
    defaults.update(kwargs)
    return BoxSourceConfig(**defaults)


# ---------------------------------------------------------------------------
# _get_box_client caching
# ---------------------------------------------------------------------------


class TestBoxClientCache:
    def test_client_cached_across_calls(self):
        """Same credentials_path returns the same cached client."""
        adapter = BoxSourceAdapter()
        mock_client = Mock()
        config = _make_config()

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.box.adapter.get_box_client",
            return_value=mock_client,
        ) as mock_get:
            c1 = adapter._get_box_client(config=config)
            c2 = adapter._get_box_client(config=config)

        assert c1 is mock_client
        assert c2 is mock_client
        mock_get.assert_called_once()

    def test_different_paths_create_different_clients(self):
        """Different credentials_path values each get their own client."""
        adapter = BoxSourceAdapter()
        client_a, client_b = Mock(), Mock()
        config_a = _make_config(credentials_path="/tmp/a.json")
        config_b = _make_config(credentials_path="/tmp/b.json")

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.box.adapter.get_box_client",
            side_effect=[client_a, client_b],
        ):
            r_a = adapter._get_box_client(config=config_a)
            r_b = adapter._get_box_client(config=config_b)

        assert r_a is client_a
        assert r_b is client_b


# ---------------------------------------------------------------------------
# _should_include_file
# ---------------------------------------------------------------------------


class TestBoxShouldIncludeFile:
    def test_no_filters_always_included(self):
        adapter = BoxSourceAdapter()
        config = _make_config()
        assert adapter._should_include_file("report.pdf", 1024, config) is True

    def test_extension_filter_excludes(self):
        adapter = BoxSourceAdapter()
        config = _make_config(file_extensions=[".pdf"])
        assert adapter._should_include_file("report.txt", 1024, config) is False

    def test_extension_filter_includes(self):
        adapter = BoxSourceAdapter()
        config = _make_config(file_extensions=[".pdf"])
        assert adapter._should_include_file("report.pdf", 1024, config) is True

    def test_max_file_size_excludes_large_files(self):
        adapter = BoxSourceAdapter()
        config = _make_config(max_file_size_mb=1)
        big_size = 2 * 1024 * 1024
        assert adapter._should_include_file("big.pdf", big_size, config) is False

    def test_max_file_size_includes_small_files(self):
        adapter = BoxSourceAdapter()
        config = _make_config(max_file_size_mb=10)
        small_size = 1024
        assert adapter._should_include_file("small.pdf", small_size, config) is True


# ---------------------------------------------------------------------------
# _parse_modified_time
# ---------------------------------------------------------------------------


class TestBoxParseModifiedTime:
    def test_returns_none_for_none_input(self):
        assert BoxSourceAdapter()._parse_modified_time(None) is None

    def test_returns_datetime_objects_unchanged(self):
        dt = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
        result = BoxSourceAdapter()._parse_modified_time(dt)
        assert result == dt

    def test_parses_iso_string_with_z(self):
        result = BoxSourceAdapter()._parse_modified_time("2024-06-01T12:00:00Z")
        assert result.year == 2024

    def test_returns_none_for_invalid_type(self):
        result = BoxSourceAdapter()._parse_modified_time(12345)
        assert result is None

    def test_returns_none_for_invalid_string(self):
        result = BoxSourceAdapter()._parse_modified_time("not-a-date")
        assert result is None


# ---------------------------------------------------------------------------
# _prepare_document
# ---------------------------------------------------------------------------


class TestBoxPrepareDocument:
    def test_returns_document_with_lazy_content(self):
        """_prepare_document should return empty bytes for content (lazy loading)."""
        adapter = BoxSourceAdapter()
        root_id = "root_folder"
        path_entries = [_make_entry("0", "All Files"), _make_entry(root_id, "root")]
        file_info = _make_file_info(
            file_id="99",
            name="invoice.pdf",
            size=2048,
            path_entries=path_entries,
        )
        doc = adapter._prepare_document(file_info=file_info, root_folder_id=root_id)

        assert doc.content == b""
        assert doc.id == "99"
        assert doc.name == "invoice.pdf"
        assert doc.metadata["box_id"] == "99"
        assert doc.metadata["source_id"] == "99"

    def test_uses_shared_link_url(self):
        adapter = BoxSourceAdapter()
        file_info = _make_file_info(
            file_id="42",
            name="doc.pdf",
            shared_link={"url": "https://box.com/s/abc123"},
        )
        doc = adapter._prepare_document(file_info=file_info, root_folder_id="0")
        assert doc.source_url == "https://box.com/s/abc123"

    def test_falls_back_to_box_url_without_shared_link(self):
        adapter = BoxSourceAdapter()
        file_info = _make_file_info(file_id="77", name="doc.pdf")
        doc = adapter._prepare_document(file_info=file_info, root_folder_id="0")
        assert "77" in doc.source_url
        assert "box.com" in doc.source_url

    def test_serializes_datetime_timestamps(self):
        adapter = BoxSourceAdapter()
        dt = datetime(2024, 1, 15, tzinfo=UTC)
        file_info = _make_file_info(file_id="1", name="f.pdf", created_at=dt, modified_at=dt)
        doc = adapter._prepare_document(file_info=file_info, root_folder_id="0")
        assert doc.metadata["created_at"] is not None
        assert doc.metadata["modified_at"] is not None


# ---------------------------------------------------------------------------
# _iter_box_files
# ---------------------------------------------------------------------------


class TestBoxIterBoxFiles:
    def test_yields_files_skipping_folders_non_recursive(self):
        adapter = BoxSourceAdapter()
        config = _make_config(recursive=False)

        mock_folder = Mock(id="0")
        file_item = types.SimpleNamespace(type="file", id="f1")
        folder_item = types.SimpleNamespace(type="folder", id="sub1")
        mock_items = types.SimpleNamespace(entries=[file_item, folder_item])
        file_info = _make_file_info(file_id="f1", name="report.pdf")

        mock_client = Mock()
        mock_client.folders.get_folder_by_id.return_value = mock_folder
        mock_client.folders.get_folder_items.return_value = mock_items
        mock_client.files.get_file_by_id.return_value = file_info

        results = list(adapter._iter_box_files(client=mock_client, config=config, folder_id="0"))
        assert len(results) == 1
        assert results[0] is file_info

    def test_skips_files_not_matching_extension(self):
        adapter = BoxSourceAdapter()
        config = _make_config(file_extensions=[".pdf"])

        mock_folder = Mock(id="0")
        file_item = types.SimpleNamespace(type="file", id="txt1")
        mock_items = types.SimpleNamespace(entries=[file_item])
        file_info = _make_file_info(file_id="txt1", name="readme.txt", size=100)

        mock_client = Mock()
        mock_client.folders.get_folder_by_id.return_value = mock_folder
        mock_client.folders.get_folder_items.return_value = mock_items
        mock_client.files.get_file_by_id.return_value = file_info

        results = list(adapter._iter_box_files(client=mock_client, config=config, folder_id="0"))
        assert results == []

    def test_raises_on_api_error(self):
        adapter = BoxSourceAdapter()
        config = _make_config()
        mock_client = Mock()
        mock_client.folders.get_folder_by_id.side_effect = RuntimeError("API error")

        with pytest.raises(RuntimeError, match="API error"):
            list(adapter._iter_box_files(client=mock_client, config=config, folder_id="0"))

    def test_skips_non_file_non_folder_items(self):
        adapter = BoxSourceAdapter()
        config = _make_config()
        mock_folder = Mock(id="0")
        unknown_item = types.SimpleNamespace(type="web_link", id="wl1")
        mock_items = types.SimpleNamespace(entries=[unknown_item])

        mock_client = Mock()
        mock_client.folders.get_folder_by_id.return_value = mock_folder
        mock_client.folders.get_folder_items.return_value = mock_items

        results = list(adapter._iter_box_files(client=mock_client, config=config, folder_id="0"))
        assert results == []


# ---------------------------------------------------------------------------
# _download_file_content
# ---------------------------------------------------------------------------


class TestBoxDownloadFileContent:
    def test_returns_bytes_on_success(self):
        adapter = BoxSourceAdapter()
        mock_stream = Mock()
        mock_stream.read.return_value = b"file bytes"
        mock_client = Mock()
        mock_client.downloads.download_file.return_value = mock_stream

        result = adapter._download_file_content(client=mock_client, file_id="123")
        assert result == b"file bytes"

    def test_raises_on_download_error(self):
        adapter = BoxSourceAdapter()
        mock_client = Mock()
        mock_client.downloads.download_file.side_effect = RuntimeError("network fail")

        with pytest.raises(RuntimeError, match="network fail"):
            adapter._download_file_content(client=mock_client, file_id="123")


# ---------------------------------------------------------------------------
# fetch_documents
# ---------------------------------------------------------------------------


class TestBoxFetchDocuments:
    @pytest.mark.asyncio
    async def test_single_file_mode(self):
        adapter = BoxSourceAdapter()
        config = _make_config(file_id="file99")
        file_info = _make_file_info(file_id="file99", name="single.pdf")

        mock_client = Mock()
        mock_client.files.get_file_by_id.return_value = file_info

        with patch.object(adapter, "_get_box_client", return_value=mock_client):
            docs = [doc async for doc in adapter.fetch_documents(config)]

        assert len(docs) == 1
        assert docs[0].id == "file99"

    @pytest.mark.asyncio
    async def test_folder_mode_with_max_files(self):
        adapter = BoxSourceAdapter()
        config = _make_config(folder_id="folder1", max_files=2)

        file_infos = [_make_file_info(file_id=str(i), name=f"doc{i}.pdf") for i in range(5)]

        with patch.object(adapter, "_get_box_client", return_value=Mock()):
            with patch.object(adapter, "_iter_box_files", return_value=iter(file_infos)):
                docs = [doc async for doc in adapter.fetch_documents(config)]

        assert len(docs) == 2

    @pytest.mark.asyncio
    async def test_raises_value_error_on_exception(self):
        adapter = BoxSourceAdapter()
        config = _make_config(folder_id="folder1")

        with patch.object(adapter, "_get_box_client", side_effect=ValueError("bad config")):
            with pytest.raises(ValueError, match="Failed to fetch documents from Box"):
                async for _ in adapter.fetch_documents(config):
                    pass


# ---------------------------------------------------------------------------
# test_connection
# ---------------------------------------------------------------------------


class TestBoxTestConnection:
    @pytest.mark.asyncio
    async def test_successful_connection(self):
        adapter = BoxSourceAdapter()
        config = _make_config()
        mock_folder = Mock()
        mock_folder.name = "All Files"
        mock_client = Mock()
        mock_client.folders.get_folder_by_id.return_value = mock_folder

        with patch.object(adapter, "_get_box_client", return_value=mock_client):
            success, msg = await adapter.test_connection(config)

        assert success is True
        assert "Successfully connected" in msg

    @pytest.mark.asyncio
    async def test_failed_connection(self):
        adapter = BoxSourceAdapter()
        config = _make_config()
        mock_client = Mock()
        mock_client.folders.get_folder_by_id.side_effect = RuntimeError("auth error")

        with patch.object(adapter, "_get_box_client", return_value=mock_client):
            success, msg = await adapter.test_connection(config)

        assert success is False
        assert "auth error" in msg

    @pytest.mark.asyncio
    async def test_import_error_returns_false(self):
        adapter = BoxSourceAdapter()
        config = _make_config()

        with patch.object(adapter, "_get_box_client", side_effect=ImportError("no box sdk")):
            success, msg = await adapter.test_connection(config)

        assert success is False
        assert "not installed" in msg


# ---------------------------------------------------------------------------
# fetch_binary_content
# ---------------------------------------------------------------------------


class TestBoxFetchBinaryContent:
    def test_fetches_content_by_file_id(self):
        adapter = BoxSourceAdapter()
        mock_client = Mock()
        mock_stream = Mock()
        mock_stream.read.return_value = b"content"
        mock_client.downloads.download_file.return_value = mock_stream

        with patch.object(adapter, "_get_box_client", return_value=mock_client):
            result = adapter.fetch_binary_content(
                source_id="702199884861",
                connection_params={},
                credentials={"credentials_json_path": "/tmp/box.json"},
            )
        assert result == b"content"

    def test_extracts_file_id_from_url(self):
        adapter = BoxSourceAdapter()
        mock_client = Mock()
        mock_stream = Mock()
        mock_stream.read.return_value = b"data"
        mock_client.downloads.download_file.return_value = mock_stream

        with patch.object(adapter, "_get_box_client", return_value=mock_client):
            result = adapter.fetch_binary_content(
                source_id="https://app.box.com/file/702199884861",
                connection_params={},
                credentials={"credentials_json_path": "/tmp/box.json"},
            )
        assert result == b"data"
        mock_client.downloads.download_file.assert_called_once_with("702199884861")

    def test_returns_none_for_malformed_url(self):
        adapter = BoxSourceAdapter()
        result = adapter.fetch_binary_content(
            source_id="https://app.box.com/bad/url",
            connection_params={},
            credentials={"credentials_json_path": "/tmp/box.json"},
        )
        assert result is None

    def test_returns_none_for_missing_credentials(self):
        adapter = BoxSourceAdapter()
        result = adapter.fetch_binary_content(
            source_id="123456",
            connection_params={},
            credentials={},
        )
        assert result is None

    def test_returns_none_on_file_not_found(self):
        adapter = BoxSourceAdapter()
        with patch.object(adapter, "_get_box_client", side_effect=FileNotFoundError("no file")):
            result = adapter.fetch_binary_content(
                source_id="123",
                connection_params={},
                credentials={"credentials_json_path": "/tmp/box.json"},
            )
        assert result is None

    def test_returns_none_on_value_error(self):
        adapter = BoxSourceAdapter()
        with patch.object(adapter, "_get_box_client", side_effect=ValueError("bad auth")):
            result = adapter.fetch_binary_content(
                source_id="123",
                connection_params={},
                credentials={"credentials_json_path": "/tmp/box.json"},
            )
        assert result is None

    def test_returns_none_on_unexpected_error(self):
        adapter = BoxSourceAdapter()
        with patch.object(adapter, "_get_box_client", side_effect=RuntimeError("unexpected")):
            result = adapter.fetch_binary_content(
                source_id="123",
                connection_params={},
                credentials={"credentials_json_path": "/tmp/box.json"},
            )
        assert result is None
