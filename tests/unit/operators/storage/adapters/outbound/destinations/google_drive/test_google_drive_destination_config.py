"""Tests for GoogleDriveDestinationConfig."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from docpipe.core.operators.storage.adapters.outbound.destinations.google_drive.config import (
    GoogleDriveDestinationConfig,
)

_SA_BASE = {
    "folder_id": "test-folder-id-12345",
    "service_account_json_path": "/path/to/sa.json",
}

_OAUTH_BASE = {
    "folder_id": "test-folder-id-12345",
    "credentials_path": "/path/to/credentials.json",
}


class TestGoogleDriveDestinationConfigRequiredFields:
    def test_valid_service_account_config(self):
        cfg = GoogleDriveDestinationConfig(**_SA_BASE)
        assert cfg.folder_id == "test-folder-id-12345"
        assert cfg.service_account_json_path == "/path/to/sa.json"

    def test_valid_oauth_config(self):
        cfg = GoogleDriveDestinationConfig(**_OAUTH_BASE)
        assert cfg.folder_id == "test-folder-id-12345"
        assert cfg.credentials_path == "/path/to/credentials.json"

    def test_missing_folder_id_raises(self):
        with pytest.raises(ValidationError):
            GoogleDriveDestinationConfig(service_account_json_path="/path/to/sa.json")

    def test_empty_folder_id_raises(self):
        with pytest.raises(ValidationError):
            GoogleDriveDestinationConfig(**{**_SA_BASE, "folder_id": "   "})

    def test_no_credentials_raises(self):
        with pytest.raises(
            ValidationError,
            match=r"service_account_json_path.*credentials_path|credentials_path.*service_account_json_path",
        ):
            GoogleDriveDestinationConfig(folder_id="abc123")

    def test_both_credentials_raises(self):
        with pytest.raises(ValidationError, match="Cannot use both"):
            GoogleDriveDestinationConfig(
                folder_id="abc123",
                service_account_json_path="/path/to/sa.json",
                credentials_path="/path/to/creds.json",
            )


class TestGoogleDriveDestinationConfigDefaults:
    def test_drive_id_default_is_none(self):
        cfg = GoogleDriveDestinationConfig(**_SA_BASE)
        assert cfg.drive_id is None

    def test_create_dirs_default_is_true(self):
        cfg = GoogleDriveDestinationConfig(**_SA_BASE)
        assert cfg.create_dirs is True

    def test_scopes_default_to_drive(self):
        cfg = GoogleDriveDestinationConfig(**_SA_BASE)
        assert cfg.scopes == ["https://www.googleapis.com/auth/drive"]

    def test_chunk_size_mb_default_is_5(self):
        cfg = GoogleDriveDestinationConfig(**_SA_BASE)
        assert cfg.chunk_size_mb == 5

    def test_token_path_default_is_none(self):
        cfg = GoogleDriveDestinationConfig(**_OAUTH_BASE)
        assert cfg.token_path is None


class TestGoogleDriveDestinationConfigPathExpansion:
    def test_tilde_expanded_in_sa_path(self):
        cfg = GoogleDriveDestinationConfig(**{**_SA_BASE, "service_account_json_path": "~/sa.json"})
        assert not cfg.service_account_json_path.startswith("~")
        assert cfg.service_account_json_path == str(Path("~/sa.json").expanduser())

    def test_tilde_expanded_in_credentials_path(self):
        cfg = GoogleDriveDestinationConfig(**{**_OAUTH_BASE, "credentials_path": "~/creds.json"})
        assert cfg.credentials_path == str(Path("~/creds.json").expanduser())


class TestGoogleDriveDestinationConfigHelpers:
    def test_is_service_account_true_for_sa_config(self):
        cfg = GoogleDriveDestinationConfig(**_SA_BASE)
        assert cfg.is_service_account() is True

    def test_is_service_account_false_for_oauth_config(self):
        cfg = GoogleDriveDestinationConfig(**_OAUTH_BASE)
        assert cfg.is_service_account() is False

    def test_get_token_path_uses_explicit_token_path(self):
        cfg = GoogleDriveDestinationConfig(**{**_OAUTH_BASE, "token_path": "/custom/token.pickle"})
        assert cfg.get_token_path() == "/custom/token.pickle"

    def test_get_token_path_derives_from_credentials_dir(self):
        cfg = GoogleDriveDestinationConfig(**{**_OAUTH_BASE, "credentials_path": "/some/dir/creds.json"})
        assert cfg.get_token_path() == "/some/dir/gdrive_token.pickle"

    def test_get_token_path_empty_for_sa_config(self):
        cfg = GoogleDriveDestinationConfig(**_SA_BASE)
        assert cfg.get_token_path() == ""


class TestGoogleDriveDestinationConfigOptionalFields:
    def test_drive_id_can_be_set(self):
        cfg = GoogleDriveDestinationConfig(**{**_SA_BASE, "drive_id": "0ABcDeFgHi"})
        assert cfg.drive_id == "0ABcDeFgHi"

    def test_custom_scopes_accepted(self):
        cfg = GoogleDriveDestinationConfig(**{**_SA_BASE, "scopes": ["https://www.googleapis.com/auth/drive"]})
        assert cfg.scopes == ["https://www.googleapis.com/auth/drive"]

    def test_chunk_size_mb_below_minimum_raises(self):
        with pytest.raises(ValidationError):
            GoogleDriveDestinationConfig(**{**_SA_BASE, "chunk_size_mb": 0})
