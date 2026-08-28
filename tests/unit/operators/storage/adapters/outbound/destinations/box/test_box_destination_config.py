"""Tests for BoxDestinationConfig."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from docpipe.core.operators.storage.adapters.outbound.destinations.box.config import (
    BoxDestinationConfig,
)

_BASE = {
    "credentials_path": "/tmp/box_config.json",
    "folder_id": "123456789",
}


class TestBoxDestinationConfigRequiredFields:
    def test_valid_config(self):
        cfg = BoxDestinationConfig(**_BASE)
        assert cfg.credentials_path == "/tmp/box_config.json"
        assert cfg.folder_id == "123456789"

    def test_missing_credentials_path_raises(self):
        with pytest.raises(ValidationError):
            BoxDestinationConfig(folder_id="123456789")

    def test_empty_folder_id_raises(self):
        with pytest.raises(ValidationError, match="folder_id cannot be empty"):
            BoxDestinationConfig(**{**_BASE, "folder_id": "   "})

    def test_blank_folder_id_raises(self):
        with pytest.raises(ValidationError, match="folder_id cannot be empty"):
            BoxDestinationConfig(**{**_BASE, "folder_id": ""})


class TestBoxDestinationConfigDefaults:
    def test_folder_id_defaults_to_root(self):
        cfg = BoxDestinationConfig(credentials_path="/tmp/box_config.json")
        assert cfg.folder_id == "0"

    def test_create_dirs_default_is_true(self):
        cfg = BoxDestinationConfig(**_BASE)
        assert cfg.create_dirs is True

    def test_create_dirs_can_be_false(self):
        cfg = BoxDestinationConfig(**{**_BASE, "create_dirs": False})
        assert cfg.create_dirs is False


class TestBoxDestinationConfigPathExpansion:
    def test_tilde_expanded_in_credentials_path(self):
        cfg = BoxDestinationConfig(**{**_BASE, "credentials_path": "~/box_config.json"})
        assert not cfg.credentials_path.startswith("~")
        assert cfg.credentials_path == str(Path("~/box_config.json").expanduser())

    def test_env_var_expanded_in_credentials_path(self, monkeypatch):
        monkeypatch.setenv("BOX_TEST_CREDS", "/tmp/from_env_box.json")
        cfg = BoxDestinationConfig(**{**_BASE, "credentials_path": "${BOX_TEST_CREDS}"})
        assert cfg.credentials_path == "/tmp/from_env_box.json"

    def test_folder_id_whitespace_stripped(self):
        cfg = BoxDestinationConfig(**{**_BASE, "folder_id": "  987654  "})
        assert cfg.folder_id == "987654"
