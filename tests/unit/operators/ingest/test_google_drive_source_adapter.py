#!/usr/bin/env python3

import asyncio
from datetime import datetime
from unittest.mock import Mock, mock_open, patch

import pytest

from docpipe.core.operators.ingest.adapters.outbound.sources.google_drive.adapter import (
    GoogleDriveSourceAdapter,
)
from docpipe.core.operators.ingest.adapters.outbound.sources.google_drive.config import (
    GoogleDriveSourceConfig,
)


async def collect_async(async_gen):
    return [item async for item in async_gen]


class TestGoogleDriveSourceConfig:
    def test_expands_credentials_path_and_default_token_path(self):
        config = GoogleDriveSourceConfig(
            credentials_path="~/creds.json",
            token_path=None,
            drive_id=None,
            folder_id="folder",
            folder_path=None,
            recursive=True,
            max_file_size_mb=None,
        )
        assert config.credentials_path.endswith("creds.json")
        assert config.get_token_path().endswith("token.json")

    def test_normalizes_extensions_and_validates_size(self):
        config = GoogleDriveSourceConfig(
            credentials_path="/tmp/creds.json",
            token_path=None,
            drive_id=None,
            folder_id=None,
            folder_path=None,
            recursive=True,
            file_extensions=["pdf", ".docx"],
            max_file_size_mb=10,
        )
        assert config.file_extensions == [".pdf", ".docx"]
        assert config.max_file_size_mb == 10

    def test_rejects_invalid_size(self):
        with pytest.raises(Exception, match="max_file_size_mb must be positive"):
            GoogleDriveSourceConfig(
                credentials_path="/tmp/creds.json",
                token_path=None,
                drive_id=None,
                folder_id=None,
                folder_path=None,
                recursive=True,
                max_file_size_mb=-1,
            )


class TestGoogleDriveSourceAdapter:
    def make_config(self):
        return GoogleDriveSourceConfig(
            credentials_path="/tmp/credentials.json",
            token_path="/tmp/token.json",
            drive_id=None,
            folder_id="folder123",
            folder_path=None,
            recursive=True,
            file_extensions=[".pdf", ".unknown"],
            max_file_size_mb=None,
        )

    def test_build_config_from_operator_params(self):
        adapter = GoogleDriveSourceAdapter()
        config = adapter.build_config_from_operator_params(
            connection_params={
                "folder_id": "folder123",
                "recursive": True,
                "drive_id": "drive1",
                "max_file_size_mb": 4,
            },
            credentials={
                "credentials_path": "/tmp/creds.json",
                "token_path": "/tmp/token.json",
                "scopes": ["scope1"],
            },
            included_extensions=["pdf"],
        )

        config_data = config.model_dump()

        assert type(config).__name__ == "GoogleDriveSourceConfig"
        assert config_data["credentials_path"] == "/tmp/creds.json"
        assert config_data["token_path"] == "/tmp/token.json"
        assert config_data["file_extensions"] == [".pdf"]
        assert config_data["drive_id"] == "drive1"
        assert config_data["max_file_size_mb"] == 4

    def test_get_credentials_from_cached_token(self):
        adapter = GoogleDriveSourceAdapter()
        config = self.make_config()
        creds = Mock(valid=True)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=b"data")),
            patch("pickle.load", return_value=creds),
        ):
            result = adapter._get_credentials(config)

        assert result is creds

    def test_get_credentials_refreshes_expired_token(self):
        adapter = GoogleDriveSourceAdapter()
        config = self.make_config()
        creds = Mock(valid=False, expired=True, refresh_token="token")

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=b"data")),
            patch("pickle.load", return_value=creds),
            patch("pickle.dump"),
        ):
            result = adapter._get_credentials(config)

        creds.refresh.assert_called_once()
        assert result is creds

    def test_get_credentials_missing_credentials_file_raises(self):
        adapter = GoogleDriveSourceAdapter()
        config = self.make_config()

        with patch("pathlib.Path.exists", side_effect=[False, False]):
            with pytest.raises(ValueError, match="Credentials file not found"):
                adapter._get_credentials(config)

    def test_fetch_documents_returns_metadata_only(self):
        """Test that fetch_documents returns documents with empty content (lazy loading)."""
        adapter = GoogleDriveSourceAdapter()
        config = self.make_config()

        # Mock file metadata from Google Drive API
        file_metadata = {
            "id": "doc1",
            "name": "file.pdf",
            "mimeType": "application/pdf",
            "size": "1024",
            "modifiedTime": "2024-01-01T10:00:00Z",
            "webViewLink": "https://drive.google.com/file/d/doc1",
        }

        with (
            patch.object(adapter, "_get_credentials", return_value=Mock()),
            patch.object(adapter, "_list_files_from_drive", return_value=[file_metadata]),
        ):
            docs = asyncio.run(collect_async(adapter.fetch_documents(config)))

        assert len(docs) == 1
        assert docs[0].id == "doc1"
        assert docs[0].name == "file.pdf"
        # Verify lazy loading - content should be empty
        assert docs[0].content == b""
        assert docs[0].size == 1024
        assert docs[0].modified_time == datetime.fromisoformat("2024-01-01T10:00:00+00:00")
        # Verify metadata is stored for lazy loading
        assert docs[0].metadata["file_id"] == "doc1"
        assert "credentials_path" not in docs[0].metadata

    def test_fetch_documents_wraps_errors(self):
        adapter = GoogleDriveSourceAdapter()
        config = self.make_config()

        with patch.object(adapter, "_get_credentials", side_effect=RuntimeError("bad auth")):
            with pytest.raises(ValueError, match="Failed to fetch documents from Google Drive"):
                asyncio.run(collect_async(adapter.fetch_documents(config)))

    def test_test_connection_success_and_failure(self):
        adapter = GoogleDriveSourceAdapter()
        config = self.make_config()

        # Mock the Google Drive API service
        mock_service = Mock()
        mock_files = Mock()
        mock_list = Mock()
        mock_list.execute.return_value = {"files": [{"id": "1", "name": "test1.pdf"}, {"id": "2", "name": "test2.pdf"}]}
        mock_files.list.return_value = mock_list
        mock_service.files.return_value = mock_files

        with (
            patch.object(adapter, "_get_credentials", return_value=Mock()),
            patch(
                "googleapiclient.discovery.build",
                return_value=mock_service,
            ),
        ):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is True
            assert "Found 2 document(s)" in message

        with patch.object(adapter, "_get_credentials", side_effect=Exception("Auth failed")):
            success, message = asyncio.run(adapter.test_connection(config))
            assert success is False
            assert "Connection test failed" in message
