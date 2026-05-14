#!/usr/bin/env python3

import asyncio
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from datasift.core.operators.ingest.adapters.outbound.sources.onedrive.adapter import (
    OneDriveSourceAdapter,
)
from datasift.core.operators.ingest.adapters.outbound.sources.onedrive.config import (
    OneDriveSourceConfig,
)
from datasift.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter import (
    SharePointSourceAdapter,
)
from datasift.core.operators.ingest.adapters.outbound.sources.sharepoint.config import (
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

    def test_fetch_documents_binary_and_text_paths(self):
        adapter = OneDriveSourceAdapter()
        config = self.make_config()

        binary_doc = Mock()
        binary_doc.metadata = {
            "id": "1",
            "source": "file1.txt",
            "modified_time": "2024-01-01T10:00:00Z",
            "size": 4,
            "mime_type": "text/plain",
            "created_time": "2024-01-01T09:00:00Z",
            "web_url": "https://example/1",
        }
        binary_doc._binary_content = b"data"
        binary_doc.page_content = "ignored"

        text_doc = Mock()
        text_doc.metadata = {"id": "2", "source": "file2.txt"}
        text_doc._binary_content = None
        text_doc.page_content = "hello"

        loader_instance = Mock()
        loader_instance.lazy_load.return_value = [binary_doc, text_doc]

        with patch(
            "datasift.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 2
        assert docs[0].content == b"data"
        assert docs[1].content == b"hello"

    def test_fetch_documents_filters_extension_and_size(self):
        adapter = OneDriveSourceAdapter()
        config = self.make_config()

        skipped_ext = Mock(
            metadata={"id": "1", "source": "file.pdf"},
            _binary_content=b"x",
            page_content="x",
        )
        skipped_size = Mock(
            metadata={"id": "2", "source": "file.txt"},
            _binary_content=b"x" * (2 * 1024 * 1024),
            page_content="x",
        )
        loader_instance = Mock()
        loader_instance.lazy_load.return_value = [skipped_ext, skipped_size]

        with patch(
            "datasift.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
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
            "datasift.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is True
            assert "Found 2 document(s)" in message

        loader_instance._get_token.return_value = None
        with patch(
            "datasift.core.operators.ingest.adapters.outbound.sources.onedrive.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert message == "Failed to acquire access token"


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

    def test_fetch_documents_maps_documents(self):
        adapter = SharePointSourceAdapter()
        config = self.make_config()

        lc_doc = Mock()
        lc_doc.metadata = {
            "id": "1",
            "source": "file1.txt",
            "modified_time": "2024-01-01T10:00:00Z",
            "size": 4,
            "mime_type": "text/plain",
            "created_time": "2024-01-01T09:00:00Z",
            "web_url": "https://example/1",
        }
        lc_doc._binary_content = b"data"
        lc_doc.page_content = "ignored"

        loader_instance = Mock()
        loader_instance.lazy_load.return_value = [lc_doc]

        with patch(
            "datasift.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            return_value=loader_instance,
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 1
        assert docs[0].metadata["document_library_id"] == "lib1"
        assert docs[0].source_url == "https://example/1"

    def test_test_connection_error_paths(self):
        adapter = SharePointSourceAdapter()
        config = self.make_config()

        with patch(
            "datasift.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            side_effect=ImportError,
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "dependencies not installed" in message

        with patch(
            "datasift.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.MicrosoftGraphLoader",
            side_effect=ValueError("bad config"),
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "Configuration error" in message
