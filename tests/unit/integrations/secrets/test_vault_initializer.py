"""Unit tests for initialize_secret_providers()."""

import os
from unittest.mock import MagicMock, patch

import pytest

from docpipe.integrations.secrets.secret_provider import clear_providers, get_provider


@pytest.fixture(autouse=True)
def _clean_providers():
    clear_providers()
    yield
    clear_providers()


def _call(*, env=None, yaml_content="secrets:\n  vault:\n    enabled: true\n    provider: hashicorp\n"):
    """Helper: run initialize_secret_providers with patched env and config."""
    env_vars = env or {}
    mock_provider = MagicMock()
    mock_provider._config.validate.return_value = None
    mock_provider._config.addr = "http://vault.test:8200"
    mock_provider._config.mount_point = "secret"
    mock_provider.is_available.return_value = True

    with (
        patch.dict(os.environ, env_vars, clear=False),
        patch("docpipe.integrations.secrets.vault_initializer.HashiCorpVaultProvider", return_value=mock_provider),
        patch("builtins.open", mock_open_yaml(yaml_content)),
        patch("pathlib.Path.exists", return_value=True),
    ):
        from docpipe.integrations.secrets.vault_initializer import initialize_secret_providers

        initialize_secret_providers()

    return mock_provider


def mock_open_yaml(content: str):
    from unittest.mock import mock_open

    return mock_open(read_data=content)


class TestInitializeSecretProviders:
    def test_disabled_via_env_var(self):
        """DOCPIPE_VAULT_ENABLED=false skips registration regardless of YAML."""
        mock_provider = _call(env={"DOCPIPE_VAULT_ENABLED": "false"})
        assert get_provider(name="hashicorp") is None
        mock_provider.is_available.assert_not_called()

    def test_disabled_when_yaml_enabled_false(self):
        """secrets.vault.enabled=false in YAML → no registration."""
        mock_provider = _call(yaml_content="secrets:\n  vault:\n    enabled: false\n")
        assert get_provider(name="hashicorp") is None
        mock_provider.is_available.assert_not_called()

    def test_disabled_when_no_secrets_section(self):
        """No secrets section in YAML → no registration."""
        mock_provider = _call(yaml_content="job_management:\n  framework:\n    type: default\n")
        assert get_provider(name="hashicorp") is None
        mock_provider.is_available.assert_not_called()

    def test_env_var_true_overrides_yaml_disabled(self):
        """DOCPIPE_VAULT_ENABLED=true enables Vault even when YAML says enabled: false."""
        env = {
            "DOCPIPE_VAULT_ENABLED": "true",
            "VAULT_ROLE_ID": "role",
            "VAULT_SECRET_ID": "secret",
        }
        _call(env=env, yaml_content="secrets:\n  vault:\n    enabled: false\n")
        assert get_provider(name="hashicorp") is not None

    def test_missing_credentials_skips_registration(self):
        """Missing VAULT_ROLE_ID/VAULT_SECRET_ID → warning, no registration."""
        from docpipe.exceptions.docpipe_exceptions import ConfigurationError

        mock_provider = MagicMock()
        mock_provider._config.validate.side_effect = ConfigurationError("VAULT_ROLE_ID must be set")

        with (
            patch.dict(os.environ, {"DOCPIPE_VAULT_ENABLED": "true"}, clear=False),
            patch("docpipe.integrations.secrets.vault_initializer.HashiCorpVaultProvider", return_value=mock_provider),
            patch("builtins.open", mock_open_yaml("secrets:\n  vault:\n    enabled: true\n")),
            patch("pathlib.Path.exists", return_value=True),
        ):
            from docpipe.integrations.secrets.vault_initializer import initialize_secret_providers

            initialize_secret_providers()

        assert get_provider(name="hashicorp") is None
        mock_provider.is_available.assert_not_called()

    def test_unreachable_vault_skips_registration(self):
        """Vault not reachable → warning, no registration."""
        mock_provider = MagicMock()
        mock_provider._config.validate.return_value = None
        mock_provider._config.addr = "http://vault.test:8200"
        mock_provider.is_available.return_value = False

        with (
            patch.dict(os.environ, {"DOCPIPE_VAULT_ENABLED": "true"}, clear=False),
            patch("docpipe.integrations.secrets.vault_initializer.HashiCorpVaultProvider", return_value=mock_provider),
            patch("builtins.open", mock_open_yaml("secrets:\n  vault:\n    enabled: true\n")),
            patch("pathlib.Path.exists", return_value=True),
        ):
            from docpipe.integrations.secrets.vault_initializer import initialize_secret_providers

            initialize_secret_providers()

        assert get_provider(name="hashicorp") is None

    def test_successful_registration(self):
        """Happy path — provider is registered under configured name."""
        env = {"DOCPIPE_VAULT_ENABLED": "true", "VAULT_ROLE_ID": "role", "VAULT_SECRET_ID": "secret"}
        _call(env=env)
        assert get_provider(name="hashicorp") is not None

    def test_custom_provider_name_from_env(self):
        """DOCPIPE_VAULT_PROVIDER_NAME overrides YAML provider name."""
        env = {
            "DOCPIPE_VAULT_ENABLED": "true",
            "DOCPIPE_VAULT_PROVIDER_NAME": "my-vault",
            "VAULT_ROLE_ID": "role",
            "VAULT_SECRET_ID": "secret",
        }
        _call(env=env)
        assert get_provider(name="my-vault") is not None
        assert get_provider(name="hashicorp") is None
