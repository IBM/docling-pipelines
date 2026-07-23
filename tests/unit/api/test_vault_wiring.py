"""Verify initialize_secret_providers() is called during API lifespan startup."""

from unittest.mock import patch

from fastapi.testclient import TestClient


class TestVaultInitializerWiring:
    @patch("docpipe.integrations.secrets.vault_initializer.initialize_secret_providers")
    def test_initialize_secret_providers_called_on_startup(self, mock_init):
        """initialize_secret_providers() must be called in the API lifespan."""
        from docpipe.api.main import app

        with TestClient(app):
            mock_init.assert_called_once()
