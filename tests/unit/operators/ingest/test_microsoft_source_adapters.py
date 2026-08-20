#!/usr/bin/env python3

import asyncio
from unittest.mock import ANY, MagicMock, Mock, patch

import pytest
from pydantic import ValidationError

from docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter import (
    OneDriveSourceAdapter,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.config import (
    OneDriveSourceConfig,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter import (
    SharePointSourceAdapter,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.config import (
    SharePointSourceConfig,
)


async def collect_async(async_gen):
    return [item async for item in async_gen]


class TestOneDriveSourceConfig:
    def test_strips_credentials_and_normalizes_fields(self):
        config = OneDriveSourceConfig(
            client_id=" client ",
            client_secret=" secret ",  # pragma: allowlist secret
            tenant_id=" tenant ",
            drive_id="test_drive_id",
            folder_path="Documents",
            recursive=True,
            file_extensions=["pdf", ".txt"],
            max_file_size_mb=None,
            graph_api_version="v1.0",
        )
        assert config.client_id == "client"
        assert config.client_secret == "secret"  # pragma: allowlist secret
        assert config.tenant_id == "tenant"
        assert config.folder_path == "/Documents"
        assert config.file_extensions == [".pdf", ".txt"]

    def test_rejects_empty_credentials(self):
        with pytest.raises(ValidationError, match="client_id cannot be empty"):
            OneDriveSourceConfig(
                client_id=" ",
                client_secret="secret",  # pragma: allowlist secret
                tenant_id="tenant",
                drive_id="test_drive_id",
                folder_path=None,
                recursive=True,
                max_file_size_mb=None,
                graph_api_version="v1.0",
            )

    def test_rejects_invalid_graph_api_version(self):
        with pytest.raises(ValidationError, match="graph_api_version must be one of"):
            OneDriveSourceConfig(
                client_id="client",
                client_secret="secret",  # pragma: allowlist secret
                tenant_id="tenant",
                drive_id="test_drive_id",
                folder_path=None,
                recursive=True,
                max_file_size_mb=None,
                graph_api_version="v2",
            )


class TestSharePointSourceConfig:
    def test_normalizes_fields(self):
        config = SharePointSourceConfig(
            client_id=" client ",
            client_secret=" secret ",  # pragma: allowlist secret
            tenant_id=" tenant ",
            document_library_id=" lib ",
            folder_path="Shared Documents",
            recursive=True,
            file_extensions=["pdf"],
            max_file_size_mb=None,
            graph_api_version="v1.0",
        )
        assert config.client_id == "client"
        assert config.client_secret == "secret"  # pragma: allowlist secret
        assert config.tenant_id == "tenant"
        assert config.document_library_id == "lib"
        assert config.folder_path == "/Shared Documents"
        assert config.file_extensions == [".pdf"]

    def test_rejects_invalid_graph_api_version(self):
        with pytest.raises(ValidationError, match="graph_api_version must be one of"):
            SharePointSourceConfig(
                client_id="client",
                client_secret="secret",  # pragma: allowlist secret
                tenant_id="tenant",
                document_library_id="lib",
                folder_path=None,
                recursive=True,
                max_file_size_mb=None,
                graph_api_version="v2",
            )


class TestOneDriveSourceAdapter:
    def make_config(self):
        return OneDriveSourceConfig(
            client_id="client",
            client_secret="secret",  # pragma: allowlist secret
            tenant_id="tenant",
            drive_id="drive1",
            folder_path="/Docs",
            recursive=True,
            file_extensions=[".txt"],
            max_file_size_mb=1,
            graph_api_version="v1.0",
        )

    def test_build_config_from_operator_params(self):
        adapter = OneDriveSourceAdapter()
        config = adapter.build_config_from_operator_params(
            connection_params={"drive_id": "drive1", "folder_path": "Docs", "recursive": False},
            credentials={"client_id": "client", "client_secret": "secret", "tenant_id": "tenant"},
            included_extensions=["txt"],
        )

        config_data = config.model_dump()

        assert type(config).__name__ == "OneDriveSourceConfig"
        assert config_data["drive_id"] == "drive1"
        assert config_data["folder_path"] == "/Docs"
        assert config_data["recursive"] is False
        assert config_data["file_extensions"] == [".txt"]

    def test_fetch_documents_returns_metadata_only(self):
        """Test that fetch_documents returns documents with empty content (lazy loading)."""
        adapter = OneDriveSourceAdapter()
        config = self.make_config()

        # Mock file metadata from Graph API
        file1 = {
            "id": "1",
            "name": "file1.txt",
            "size": 1024,
            "lastModifiedDateTime": "2024-01-01T10:00:00Z",
            "createdDateTime": "2024-01-01T09:00:00Z",
            "webUrl": "https://example/1",
            "file": {"mimeType": "text/plain"},
        }

        file2 = {
            "id": "2",
            "name": "file2.txt",
            "size": 2048,
            "lastModifiedDateTime": "2024-01-02T10:00:00Z",
            "createdDateTime": "2024-01-02T09:00:00Z",
            "webUrl": "https://example/2",
            "file": {"mimeType": "text/plain"},
        }

        loader_instance = Mock()
        loader_instance._get_token.return_value = "mock_token"
        loader_instance._rest_client = Mock()
        loader_instance._list_files.return_value = [file1, file2]

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 2
        # Verify lazy loading - content should be empty
        assert docs[0].content == b""
        assert docs[1].content == b""
        # Verify metadata is stored
        assert docs[0].id == "1"
        assert docs[0].name == "file1.txt"
        assert docs[0].size == 1024
        assert docs[0].metadata["item_id"] == "1"
        assert docs[0].metadata["client_id"] == "client"
        assert docs[1].id == "2"

    def test_fetch_documents_filters_extension_and_size(self):
        """Test that file extension and size filters work correctly."""
        adapter = OneDriveSourceAdapter()
        config = self.make_config()

        # File with wrong extension (should be skipped)
        skipped_ext = {
            "id": "1",
            "name": "file.pdf",
            "size": 100,
            "file": {"mimeType": "application/pdf"},
        }

        # File too large (should be skipped)
        skipped_size = {
            "id": "2",
            "name": "file.txt",
            "size": 2 * 1024 * 1024,  # 2MB, config max is 1MB
            "file": {"mimeType": "text/plain"},
        }

        loader_instance = Mock()
        loader_instance._get_token.return_value = "mock_token"
        loader_instance._rest_client = Mock()
        loader_instance._list_files.return_value = [skipped_ext, skipped_size]

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert docs == []

    def test_test_connection_variants(self):
        adapter = OneDriveSourceAdapter()
        config = self.make_config()

        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance.lazy_load.return_value = [Mock(), Mock()]

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is True
            assert "Found 2 document(s)" in message

        loader_instance._get_token.return_value = None
        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert message == "Failed to acquire access token"

    def test_resolve_onedrive_item_id_returns_direct_path(self):
        adapter = OneDriveSourceAdapter()
        item_id, drive_id = adapter._resolve_onedrive_item_id(
            file_path="item123",
            drive_id="drive1",
            loader=Mock(),
            token="token",
        )

        assert item_id == "item123"
        assert drive_id == "drive1"

    def test_resolve_onedrive_item_id_raises_for_invalid_url(self):
        adapter = OneDriveSourceAdapter()

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.extract_msgraph_file_id_from_url",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="Could not extract file ID"):
                adapter._resolve_onedrive_item_id(
                    file_path="https://example/invalid",
                    drive_id="drive1",
                    loader=Mock(),
                    token="token",
                )

    def test_resolve_folder_item_id_returns_id(self):
        loader = Mock()
        loader._rest_client.call_rest_json.return_value = {"id": "folder123"}

        folder_id = OneDriveSourceAdapter._resolve_folder_item_id(
            loader=loader,
            drive_id="drive1",
            folder_path="/Docs",
            headers={"Authorization": "Bearer token"},
        )

        assert folder_id == "folder123"

    def test_resolve_folder_item_id_raises_value_error_on_missing_folder(self):
        loader = Mock()
        loader._rest_client.call_rest_json.side_effect = RuntimeError("not found")

        with pytest.raises(ValueError, match="Folder path '/Docs' not found"):
            OneDriveSourceAdapter._resolve_folder_item_id(
                loader=loader,
                drive_id="drive1",
                folder_path="/Docs",
                headers={"Authorization": "Bearer token"},
            )

    def test_fetch_binary_content_returns_none_when_missing_required_params(self):
        adapter = OneDriveSourceAdapter()

        result = adapter.fetch_binary_content(
            source_id="item123",
            connection_params={"drive_id": "drive1"},
            credentials={"client_id": "client"},
        )

        assert result is None

    def test_fetch_binary_content_uses_content_endpoint_without_download_url(self):
        adapter = OneDriveSourceAdapter()
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client.call_rest_json.return_value = {}
        response = MagicMock()
        response.content = b"payload"
        loader_instance._rest_client.call_rest.return_value = response

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            result = adapter.fetch_binary_content(
                source_id="item123",
                connection_params={"drive_id": "drive1"},
                credentials={
                    "client_id": "client",
                    "client_secret": "secret",  # pragma: allowlist secret
                    "tenant_id": "tenant",
                },
            )

        assert result == b"payload"
        loader_instance._rest_client.call_rest.assert_called_once()

    def test_fetch_documents_single_file_uses_resolved_drive_id(self):
        adapter = OneDriveSourceAdapter()
        config = OneDriveSourceConfig(
            client_id="client",
            client_secret="secret",  # pragma: allowlist secret
            tenant_id="tenant",
            drive_id="drive1",
            file_path="https://example/file/123",
            folder_path=None,
            recursive=False,
            max_file_size_mb=None,
            graph_api_version="v1.0",
        )
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client.call_rest_json.return_value = {
            "id": "item123",
            "name": "single.txt",
            "size": 99,
            "webUrl": "https://example/single.txt",
            "file": {"mimeType": "text/plain"},
        }

        with (
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
                return_value=loader_instance,
            ),
            patch.object(adapter, "_resolve_onedrive_item_id", return_value=("item123", "resolved-drive")),
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 1
        assert docs[0].metadata["drive_id"] == "resolved-drive"
        assert "source_id" not in docs[0].metadata
        loader_instance._rest_client.call_rest_json.assert_called_once_with(
            method=ANY,
            url="/drives/resolved-drive/items/item123",
            headers={"Authorization": "Bearer token"},
        )

    def test_resolve_onedrive_item_id_resolves_url_to_item_and_drive(self):
        adapter = OneDriveSourceAdapter()
        loader = Mock()
        loader._rest_client = Mock()

        with (
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.extract_msgraph_file_id_from_url",
                return_value="file123",
            ),
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.resolve_msgraph_file_id_to_item_id",
                return_value=("item123", "resolved-drive"),
            ),
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.handle_msgraph_resolution_result",
                return_value=("item123", "resolved-drive"),
            ) as mock_handle,
        ):
            item_id, drive_id = adapter._resolve_onedrive_item_id(
                file_path="https://example/file/123",
                drive_id="drive1",
                loader=loader,
                token="token",
            )

        assert item_id == "item123"
        assert drive_id == "resolved-drive"
        mock_handle.assert_called_once_with(
            file_id="file123",
            item_id="item123",
            actual_drive_id="resolved-drive",
            fallback_drive_id="drive1",
            allow_guid_fallback=False,
            original_url="https://example/file/123",
        )

    def test_fetch_documents_wraps_folder_errors(self):
        adapter = OneDriveSourceAdapter()
        config = self.make_config()
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client = Mock()

        with (
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
                return_value=loader_instance,
            ),
            patch.object(adapter, "_resolve_folder_item_id", side_effect=RuntimeError("bad folder")),
        ):
            with pytest.raises(ValueError, match="Failed to fetch documents from OneDrive"):
                asyncio.run(collect_async(adapter.fetch_documents(config)))

    def test_test_connection_covers_import_value_and_generic_errors(self):
        adapter = OneDriveSourceAdapter()
        config = self.make_config()

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            side_effect=ImportError,
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "dependencies not installed" in message

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            side_effect=ValueError("bad config"),
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "Configuration error" in message

        loader_instance = Mock()
        loader_instance._get_token.side_effect = RuntimeError("boom")
        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "Connection test failed" in message

    def test_fetch_binary_content_uses_download_url_when_available(self):
        adapter = OneDriveSourceAdapter()
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client.call_rest_json.return_value = {
            "@microsoft.graph.downloadUrl": "https://download.example/file"
        }
        response = MagicMock()
        response.content = b"payload"

        with (
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
                return_value=loader_instance,
            ),
            patch("docpipe.integrations.rest_client.RestClient") as mock_rest_client,
        ):
            mock_rest_client.return_value.call_rest.return_value = response
            result = adapter.fetch_binary_content(
                source_id="item123",
                connection_params={"drive_id": "drive1"},
                credentials={
                    "client_id": "client",
                    "client_secret": "secret",  # pragma: allowlist secret
                    "tenant_id": "tenant",
                },
            )

        assert result == b"payload"
        mock_rest_client.return_value.call_rest.assert_called_once_with(
            method=ANY,
            url="https://download.example/file",
        )

    def test_fetch_binary_content_extracts_item_id_from_web_url(self):
        adapter = OneDriveSourceAdapter()
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client.call_rest_json.return_value = {}
        response = MagicMock()
        response.content = b"payload"
        loader_instance._rest_client.call_rest.return_value = response

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            result = adapter.fetch_binary_content(
                source_id="https://example/item/123",
                connection_params={"drive_id": "drive1"},
                credentials={
                    "client_id": "client",
                    "client_secret": "secret",  # pragma: allowlist secret
                    "tenant_id": "tenant",
                    "item_id": "item123",
                },
            )

        assert result == b"payload"
        loader_instance._rest_client.call_rest_json.assert_called_once_with(
            method=ANY,
            url="/drives/drive1/items/item123",
            headers={"Authorization": "Bearer token"},
        )


class TestSharePointSourceAdapter:
    def make_config(self):
        return SharePointSourceConfig(
            client_id="client",
            client_secret="secret",  # pragma: allowlist secret
            tenant_id="tenant",
            document_library_id="lib1",
            folder_path="/Docs",
            recursive=True,
            file_extensions=[".txt"],
            max_file_size_mb=1,
            graph_api_version="v1.0",
        )

    def test_build_config_from_operator_params(self):
        adapter = SharePointSourceAdapter()
        config = adapter.build_config_from_operator_params(
            connection_params={"document_library_id": "lib1", "folder_path": "Docs", "recursive": False},
            credentials={"client_id": "client", "client_secret": "secret", "tenant_id": "tenant"},
            included_extensions=["txt"],
        )

        config_data = config.model_dump()

        assert type(config).__name__ == "SharePointSourceConfig"
        assert config_data["document_library_id"] == "lib1"
        assert config_data["folder_path"] == "/Docs"
        assert config_data["recursive"] is False
        assert config_data["file_extensions"] == [".txt"]

    def test_fetch_documents_returns_metadata_only(self):
        """Test that fetch_documents returns documents with empty content (lazy loading)."""
        adapter = SharePointSourceAdapter()
        config = self.make_config()

        # Mock file metadata from Graph API
        file1 = {
            "id": "1",
            "name": "file1.txt",
            "size": 1024,
            "lastModifiedDateTime": "2024-01-01T10:00:00Z",
            "createdDateTime": "2024-01-01T09:00:00Z",
            "webUrl": "https://example/1",
            "file": {"mimeType": "text/plain"},
        }

        loader_instance = Mock()
        loader_instance._get_token.return_value = "mock_token"
        loader_instance._rest_client = Mock()
        loader_instance._list_files.return_value = [file1]

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 1
        # Verify lazy loading - content should be empty
        assert docs[0].content == b""
        # Verify metadata is stored
        assert docs[0].metadata["document_library_id"] == "lib1"
        assert docs[0].metadata["item_id"] == "1"
        assert docs[0].source_url == "https://example/1"
        assert docs[0].size == 1024

    def test_test_connection_error_paths(self):
        adapter = SharePointSourceAdapter()
        config = self.make_config()

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            side_effect=ImportError,
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "dependencies not installed" in message

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            side_effect=ValueError("bad config"),
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "Configuration error" in message

    def test_resolve_sharepoint_item_id_returns_direct_path(self):
        adapter = SharePointSourceAdapter()
        item_id, document_library_id = adapter._resolve_sharepoint_item_id(
            file_path="item123",
            document_library_id="lib1",
            loader=Mock(),
            token="token",
        )

        assert item_id == "item123"
        assert document_library_id == "lib1"

    def test_resolve_sharepoint_item_id_raises_for_invalid_url(self):
        adapter = SharePointSourceAdapter()

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.extract_msgraph_file_id_from_url",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="Could not extract file ID"):
                adapter._resolve_sharepoint_item_id(
                    file_path="https://example/invalid",
                    document_library_id="lib1",
                    loader=Mock(),
                    token="token",
                )

    def test_resolve_sharepoint_folder_item_id_returns_id(self):
        loader = Mock()
        loader._rest_client.call_rest_json.return_value = {"id": "folder123"}

        folder_id = SharePointSourceAdapter._resolve_sharepoint_folder_item_id(
            loader=loader,
            document_library_id="lib1",
            folder_path="/Docs",
            headers={"Authorization": "Bearer token"},
        )

        assert folder_id == "folder123"

    def test_resolve_sharepoint_folder_item_id_raises_value_error_on_missing_folder(self):
        loader = Mock()
        loader._rest_client.call_rest_json.side_effect = RuntimeError("not found")

        with pytest.raises(ValueError, match="Folder path '/Docs' not found"):
            SharePointSourceAdapter._resolve_sharepoint_folder_item_id(
                loader=loader,
                document_library_id="lib1",
                folder_path="/Docs",
                headers={"Authorization": "Bearer token"},
            )

    def test_fetch_binary_content_returns_none_when_missing_required_params(self):
        adapter = SharePointSourceAdapter()

        result = adapter.fetch_binary_content(
            source_id="item123",
            connection_params={"document_library_id": "lib1"},
            credentials={"client_id": "client"},
        )

        assert result is None

    def test_fetch_binary_content_uses_content_endpoint_without_download_url(self):
        adapter = SharePointSourceAdapter()
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client.call_rest_json.return_value = {}
        response = MagicMock()
        response.content = b"payload"
        loader_instance._rest_client.call_rest.return_value = response

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            result = adapter.fetch_binary_content(
                source_id="item123",
                connection_params={"document_library_id": "lib1"},
                credentials={
                    "client_id": "client",
                    "client_secret": "secret",  # pragma: allowlist secret
                    "tenant_id": "tenant",
                },
            )

        assert result == b"payload"
        loader_instance._rest_client.call_rest.assert_called_once()

    def test_fetch_documents_single_file_uses_resolved_document_library_id(self):
        adapter = SharePointSourceAdapter()
        config = SharePointSourceConfig(
            client_id="client",
            client_secret="secret",  # pragma: allowlist secret
            tenant_id="tenant",
            document_library_id="lib1",
            file_path="https://example/file/123",
            folder_path=None,
            recursive=False,
            max_file_size_mb=None,
            graph_api_version="v1.0",
        )
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client.call_rest_json.return_value = {
            "id": "item123",
            "name": "single.txt",
            "size": 99,
            "webUrl": "https://example/single.txt",
            "file": {"mimeType": "text/plain"},
        }

        with (
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
                return_value=loader_instance,
            ),
            patch.object(adapter, "_resolve_sharepoint_item_id", return_value=("item123", "resolved-lib")),
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 1
        assert docs[0].metadata["document_library_id"] == "resolved-lib"
        assert "source_id" not in docs[0].metadata
        loader_instance._rest_client.call_rest_json.assert_called_once_with(
            method=ANY,
            url="/drives/resolved-lib/items/item123",
            headers={"Authorization": "Bearer token"},
        )

    def test_resolve_sharepoint_item_id_resolves_url_to_item_and_library(self):
        adapter = SharePointSourceAdapter()
        loader = Mock()
        loader._rest_client = Mock()

        with (
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.extract_msgraph_file_id_from_url",
                return_value="file123",
            ),
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.resolve_msgraph_file_id_to_item_id",
                return_value=("item123", "resolved-lib"),
            ),
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.handle_msgraph_resolution_result",
                return_value=("item123", "resolved-lib"),
            ) as mock_handle,
        ):
            item_id, document_library_id = adapter._resolve_sharepoint_item_id(
                file_path="https://example/file/123",
                document_library_id="lib1",
                loader=loader,
                token="token",
            )

        assert item_id == "item123"
        assert document_library_id == "resolved-lib"
        mock_handle.assert_called_once_with(
            file_id="file123",
            item_id="item123",
            actual_drive_id="resolved-lib",
            fallback_drive_id="lib1",
            allow_guid_fallback=True,
            original_url="https://example/file/123",
        )

    def test_fetch_documents_filters_sharepoint_items(self):
        adapter = SharePointSourceAdapter()
        config = self.make_config()
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client = Mock()
        loader_instance._list_files.return_value = [
            {
                "id": "1",
                "name": "skip.pdf",
                "size": 10,
                "file": {"mimeType": "application/pdf"},
            },
            {
                "id": "2",
                "name": "keep.txt",
                "size": 20,
                "lastModifiedDateTime": "2024-01-01T10:00:00Z",
                "createdDateTime": "2024-01-01T09:00:00Z",
                "webUrl": "https://example/2",
                "file": {"mimeType": "text/plain"},
            },
        ]

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 1
        assert docs[0].id == "2"

    def test_test_connection_success(self):
        adapter = SharePointSourceAdapter()
        config = self.make_config()
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance.lazy_load.return_value = [Mock(), Mock()]

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            success, message = asyncio.run(adapter.test_connection(config))

        assert success is True
        assert "Found 2 document(s)" in message

    def test_fetch_binary_content_uses_download_url_when_available(self):
        adapter = SharePointSourceAdapter()
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client.call_rest_json.return_value = {
            "@microsoft.graph.downloadUrl": "https://download.example/file"
        }
        response = MagicMock()
        response.content = b"payload"

        with (
            patch(
                "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
                return_value=loader_instance,
            ),
            patch("docpipe.integrations.rest_client.RestClient") as mock_rest_client,
        ):
            mock_rest_client.return_value.call_rest.return_value = response
            result = adapter.fetch_binary_content(
                source_id="item123",
                connection_params={"document_library_id": "lib1"},
                credentials={
                    "client_id": "client",
                    "client_secret": "secret",  # pragma: allowlist secret
                    "tenant_id": "tenant",
                },
            )

        assert result == b"payload"
        mock_rest_client.return_value.call_rest.assert_called_once_with(
            method=ANY,
            url="https://download.example/file",
        )

    def test_fetch_binary_content_extracts_item_id_from_web_url(self):
        adapter = SharePointSourceAdapter()
        loader_instance = Mock()
        loader_instance._get_token.return_value = "token"
        loader_instance._rest_client.call_rest_json.return_value = {}
        response = MagicMock()
        response.content = b"payload"
        loader_instance._rest_client.call_rest.return_value = response

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            result = adapter.fetch_binary_content(
                source_id="https://example/item/123",
                connection_params={"document_library_id": "lib1"},
                credentials={
                    "client_id": "client",
                    "client_secret": "secret",  # pragma: allowlist secret
                    "tenant_id": "tenant",
                    "item_id": "item123",
                },
            )

        assert result == b"payload"
        loader_instance._rest_client.call_rest_json.assert_called_once_with(
            method=ANY,
            url="/drives/lib1/items/item123",
            headers={"Authorization": "Bearer token"},
        )
