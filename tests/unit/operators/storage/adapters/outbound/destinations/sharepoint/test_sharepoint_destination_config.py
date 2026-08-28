"""Tests for SharePointDestinationConfig."""

import pytest
from pydantic import ValidationError

from docpipe.core.operators.storage.adapters.outbound.destinations.sharepoint.config import (
    SharePointDestinationConfig,
)

_VALID = {
    "client_id": "app-client-id",
    "client_secret": "app-client-secret",  # pragma: allowlist secret
    "tenant_id": "tenant-id",
    "drive_id": "b!abc123",
}


class TestSharePointDestinationConfigRequiredFields:
    def test_valid_minimal_config(self):
        cfg = SharePointDestinationConfig(**_VALID)
        assert cfg.client_id == "app-client-id"
        assert cfg.client_secret == "app-client-secret"  # pragma: allowlist secret
        assert cfg.tenant_id == "tenant-id"
        assert cfg.drive_id == "b!abc123"

    def test_missing_client_id_raises(self):
        params = {k: v for k, v in _VALID.items() if k != "client_id"}
        with pytest.raises(ValidationError):
            SharePointDestinationConfig(**params)

    def test_missing_client_secret_raises(self):
        params = {k: v for k, v in _VALID.items() if k != "client_secret"}
        with pytest.raises(ValidationError):
            SharePointDestinationConfig(**params)

    def test_missing_tenant_id_raises(self):
        params = {k: v for k, v in _VALID.items() if k != "tenant_id"}
        with pytest.raises(ValidationError):
            SharePointDestinationConfig(**params)

    def test_missing_drive_id_raises(self):
        params = {k: v for k, v in _VALID.items() if k != "drive_id"}
        with pytest.raises(ValidationError):
            SharePointDestinationConfig(**params)

    def test_empty_client_id_raises(self):
        with pytest.raises(ValidationError):
            SharePointDestinationConfig(**{**_VALID, "client_id": "   "})

    def test_empty_drive_id_raises(self):
        with pytest.raises(ValidationError):
            SharePointDestinationConfig(**{**_VALID, "drive_id": ""})


class TestSharePointDestinationConfigDefaults:
    def test_folder_path_default_is_empty(self):
        cfg = SharePointDestinationConfig(**_VALID)
        assert cfg.folder_path == ""

    def test_create_dirs_default_is_true(self):
        cfg = SharePointDestinationConfig(**_VALID)
        assert cfg.create_dirs is True

    def test_graph_api_version_default_is_v1(self):
        cfg = SharePointDestinationConfig(**_VALID)
        assert cfg.graph_api_version == "v1.0"


class TestSharePointDestinationConfigFolderPathNormalisation:
    def test_leading_slash_added_when_missing(self):
        cfg = SharePointDestinationConfig(**_VALID, folder_path="Processed Documents")
        assert cfg.folder_path == "/Processed Documents"

    def test_trailing_slash_stripped(self):
        cfg = SharePointDestinationConfig(**_VALID, folder_path="/Processed Documents/")
        assert cfg.folder_path == "/Processed Documents"

    def test_whitespace_stripped(self):
        cfg = SharePointDestinationConfig(**_VALID, folder_path="  /Output  ")
        assert cfg.folder_path == "/Output"

    def test_empty_folder_path_stays_empty(self):
        cfg = SharePointDestinationConfig(**_VALID, folder_path="")
        assert cfg.folder_path == ""


class TestSharePointDestinationConfigGraphApiVersionValidation:
    def test_v1_accepted(self):
        cfg = SharePointDestinationConfig(**_VALID, graph_api_version="v1.0")
        assert cfg.graph_api_version == "v1.0"

    def test_beta_accepted(self):
        cfg = SharePointDestinationConfig(**_VALID, graph_api_version="beta")
        assert cfg.graph_api_version == "beta"

    def test_invalid_version_raises(self):
        with pytest.raises(ValidationError, match="graph_api_version"):
            SharePointDestinationConfig(**_VALID, graph_api_version="v2.0")
