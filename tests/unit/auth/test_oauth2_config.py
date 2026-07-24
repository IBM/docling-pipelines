"""Unit tests for OAuth2 configuration."""

from docpipe.api.auth.oauth2_config import (
    AzureADOAuth2Config,
    GoogleOAuth2Config,
    OAuth2Config,
    get_oauth2_config,
)


class TestOAuth2Config:
    """Test OAuth2 configuration."""

    def test_oauth2_config_defaults(self):
        """Test OAuth2 config with default values."""
        config = OAuth2Config()

        assert config.oauth2_enabled is False
        assert config.oauth2_provider == "generic"
        assert config.oauth2_scope == "openid profile email"
        assert config.oauth2_session_expire_minutes == 60

    def test_oauth2_config_custom_values(self):
        """Test OAuth2 config with custom values."""
        config = OAuth2Config(
            oauth2_enabled=True,
            oauth2_provider="custom",
            oauth2_client_id="test-client-id",
            oauth2_client_secret="test-secret",
            oauth2_redirect_uri="http://localhost:8000/callback",
        )

        assert config.oauth2_enabled is True
        assert config.oauth2_provider == "custom"
        assert config.oauth2_client_id == "test-client-id"
        assert config.oauth2_client_secret == "test-secret"
        assert config.oauth2_redirect_uri == "http://localhost:8000/callback"

    def test_oauth2_config_oidc_settings(self):
        """Test OIDC-specific settings."""
        config = OAuth2Config(
            oidc_issuer="https://issuer.example.com",
            oidc_audience="test-audience",
        )

        assert config.oidc_issuer == "https://issuer.example.com"
        assert config.oidc_audience == "test-audience"


class TestGoogleOAuth2Config:
    """Test Google OAuth2 configuration."""

    def test_google_config_defaults(self):
        """Test Google config has correct defaults."""
        config = GoogleOAuth2Config()

        assert config.oauth2_provider == "google"
        assert config.oauth2_discovery_url == "https://accounts.google.com/.well-known/openid-configuration"
        assert config.oauth2_authorization_endpoint == "https://accounts.google.com/o/oauth2/v2/auth"
        assert config.oauth2_token_endpoint == "https://oauth2.googleapis.com/token"
        assert config.oauth2_userinfo_endpoint == "https://openidconnect.googleapis.com/v1/userinfo"
        assert config.oauth2_jwks_uri == "https://www.googleapis.com/oauth2/v3/certs"
        assert config.oidc_issuer == "https://accounts.google.com"

    def test_google_config_with_client_credentials(self):
        """Test Google config with client credentials."""
        config = GoogleOAuth2Config(
            oauth2_client_id="google-client-id",
            oauth2_client_secret="google-secret",
            oauth2_redirect_uri="http://localhost:8000/callback",
        )

        assert config.oauth2_client_id == "google-client-id"
        assert config.oauth2_client_secret == "google-secret"
        assert config.oauth2_redirect_uri == "http://localhost:8000/callback"
        # Provider-specific defaults should still be set
        assert config.oauth2_provider == "google"


class TestAzureADOAuth2Config:
    """Test Azure AD OAuth2 configuration."""

    def test_azure_config_defaults(self):
        """Test Azure config has correct defaults."""
        config = AzureADOAuth2Config()

        assert config.oauth2_provider == "azure"
        assert config.azure_tenant_id == "common"

    def test_azure_config_discovery_url(self):
        """Test Azure discovery URL generation."""
        config = AzureADOAuth2Config(azure_tenant_id="test-tenant-id")

        expected_url = "https://login.microsoftonline.com/test-tenant-id/v2.0/.well-known/openid-configuration"
        assert config.oauth2_discovery_url == expected_url

    def test_azure_config_authorization_endpoint(self):
        """Test Azure authorization endpoint generation."""
        config = AzureADOAuth2Config(azure_tenant_id="test-tenant-id")

        expected_url = "https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/authorize"
        assert config.oauth2_authorization_endpoint == expected_url

    def test_azure_config_token_endpoint(self):
        """Test Azure token endpoint generation."""
        config = AzureADOAuth2Config(azure_tenant_id="test-tenant-id")

        expected_url = "https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token"
        assert config.oauth2_token_endpoint == expected_url

    def test_azure_config_userinfo_endpoint(self):
        """Test Azure userinfo endpoint."""
        config = AzureADOAuth2Config()

        assert config.oauth2_userinfo_endpoint == "https://graph.microsoft.com/oidc/userinfo"

    def test_azure_config_jwks_uri(self):
        """Test Azure JWKS URI generation."""
        config = AzureADOAuth2Config(azure_tenant_id="test-tenant-id")

        expected_url = "https://login.microsoftonline.com/test-tenant-id/discovery/v2.0/keys"
        assert config.oauth2_jwks_uri == expected_url

    def test_azure_config_issuer(self):
        """Test Azure issuer generation."""
        config = AzureADOAuth2Config(azure_tenant_id="test-tenant-id")

        expected_issuer = "https://login.microsoftonline.com/test-tenant-id/v2.0"
        assert config.oidc_issuer == expected_issuer

    def test_azure_config_common_tenant(self):
        """Test Azure config with common tenant."""
        config = AzureADOAuth2Config()

        assert "common" in config.oauth2_discovery_url
        assert "common" in config.oauth2_authorization_endpoint
        assert "common" in config.oauth2_token_endpoint


class TestGetOAuth2Config:
    """Test OAuth2 config factory function."""

    def test_get_config_google(self):
        """Test getting Google config."""
        config = get_oauth2_config("google")

        assert isinstance(config, GoogleOAuth2Config)
        assert config.oauth2_provider == "google"

    def test_get_config_azure(self):
        """Test getting Azure config."""
        config = get_oauth2_config("azure")

        assert isinstance(config, AzureADOAuth2Config)
        assert config.oauth2_provider == "azure"

    def test_get_config_generic(self):
        """Test getting generic config."""
        config = get_oauth2_config("generic")

        assert isinstance(config, OAuth2Config)
        assert config.oauth2_provider == "generic"

    def test_get_config_unknown_provider(self):
        """Test getting config for unknown provider returns generic."""
        config = get_oauth2_config("unknown")

        assert isinstance(config, OAuth2Config)

    def test_get_config_none_provider(self):
        """Test getting config with None provider."""
        config = get_oauth2_config(None)

        assert isinstance(config, OAuth2Config)

    def test_get_config_case_insensitive(self):
        """Test provider name is case insensitive."""
        config_upper = get_oauth2_config("GOOGLE")
        config_lower = get_oauth2_config("google")
        config_mixed = get_oauth2_config("Google")

        # All should return GoogleOAuth2Config
        assert isinstance(config_upper, OAuth2Config)
        assert isinstance(config_lower, GoogleOAuth2Config)
        assert isinstance(config_mixed, OAuth2Config)
