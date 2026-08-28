"""Unit tests for GoogleDriveSourceConfig.get_token_path() — EC-3 coverage."""

import pytest

from docpipe.core.operators.ingest.adapters.outbound.sources.google_drive.config import GoogleDriveSourceConfig


@pytest.fixture
def oauth_config(tmp_path):
    """GoogleDriveSourceConfig using OAuth credentials."""
    creds = tmp_path / "credentials.json"
    creds.write_text("{}")
    return GoogleDriveSourceConfig(credentials_path=str(creds))


@pytest.fixture
def service_account_config(tmp_path):
    """GoogleDriveSourceConfig using service account credentials."""
    sa = tmp_path / "service_account.json"
    sa.write_text("{}")
    return GoogleDriveSourceConfig(service_account_json_path=str(sa))


class TestGetTokenPath:
    """Tests for GoogleDriveSourceConfig.get_token_path()."""

    def test_get_token_path_returns_str_when_token_path_set(self, tmp_path):
        """EC-3: get_token_path() must return str when token_path is set."""
        creds = tmp_path / "credentials.json"
        creds.write_text("{}")
        config = GoogleDriveSourceConfig(
            credentials_path=str(creds),
            token_path="~/my_token.json",
        )
        result = config.get_token_path()
        assert isinstance(result, str)
        assert not result.startswith("~")

    def test_get_token_path_derives_from_credentials_path(self, oauth_config):
        """EC-3: get_token_path() derives token.json from credentials directory."""
        result = oauth_config.get_token_path()
        assert isinstance(result, str)
        assert result.endswith("token.json")
        assert not result.startswith("~")

    def test_get_token_path_same_dir_as_credentials(self, tmp_path):
        """get_token_path() places token.json in same directory as credentials."""
        creds = tmp_path / "creds" / "credentials.json"
        creds.parent.mkdir(parents=True)
        creds.write_text("{}")
        config = GoogleDriveSourceConfig(credentials_path=str(creds))
        result = config.get_token_path()
        assert result == str(tmp_path / "creds" / "token.json")

    def test_get_token_path_empty_for_service_account(self, service_account_config):
        """get_token_path() returns empty string for service account auth."""
        result = service_account_config.get_token_path()
        assert result == ""
        assert isinstance(result, str)

    def test_get_token_path_explicit_token_path_overrides_credentials(self, tmp_path):
        """Explicit token_path takes precedence over credentials-derived path."""
        creds = tmp_path / "credentials.json"
        creds.write_text("{}")
        token = tmp_path / "tokens" / "my.json"
        config = GoogleDriveSourceConfig(
            credentials_path=str(creds),
            token_path=str(token),
        )
        result = config.get_token_path()
        assert isinstance(result, str)
        assert result == str(token)
