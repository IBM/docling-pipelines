"""Unit tests for OAuth2 provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docpipe.api.auth.models import User
from docpipe.api.auth.oauth2_config import (
    AzureADOAuth2Config,
    GoogleOAuth2Config,
    OAuth2Config,
)
from docpipe.api.auth.oauth2_provider import (
    AzureADOAuth2Provider,
    GenericOIDCProvider,
    GoogleOAuth2Provider,
    get_oauth2_provider,
)


@pytest.fixture
def oauth2_config():
    """Create OAuth2 configuration for testing."""
    return OAuth2Config(
        oauth2_enabled=True,
        oauth2_provider="generic",
        oauth2_client_id="test-client-id",
        oauth2_client_secret="test-secret",
        oauth2_redirect_uri="http://localhost:8000/callback",
        oauth2_authorization_endpoint="https://provider.com/authorize",
        oauth2_token_endpoint="https://provider.com/token",
        oauth2_userinfo_endpoint="https://provider.com/userinfo",
        oauth2_jwks_uri="https://provider.com/jwks",
        oidc_issuer="https://provider.com",
        oidc_audience="test-client-id",
    )


@pytest.fixture
def google_config():
    """Create Google OAuth2 configuration for testing."""
    return GoogleOAuth2Config(
        oauth2_enabled=True,
        oauth2_client_id="google-client-id",
        oauth2_client_secret="google-secret",
        oauth2_redirect_uri="http://localhost:8000/callback",
    )


@pytest.fixture
def azure_config():
    """Create Azure AD OAuth2 configuration for testing."""
    return AzureADOAuth2Config(
        oauth2_enabled=True,
        azure_tenant_id="test-tenant",
        oauth2_client_id="azure-client-id",
        oauth2_client_secret="azure-secret",
        oauth2_redirect_uri="http://localhost:8000/callback",
    )


class TestGoogleOAuth2Provider:
    """Test Google OAuth2 provider."""

    def test_provider_name(self, google_config):
        """Test provider name."""
        provider = GoogleOAuth2Provider(google_config)
        assert provider.get_provider_name() == "google"

    def test_generate_authorization_url(self, google_config):
        """Test authorization URL generation."""
        provider = GoogleOAuth2Provider(google_config)
        auth_url, state = provider.generate_authorization_url()

        assert "accounts.google.com" in auth_url
        assert "client_id=google-client-id" in auth_url
        assert "redirect_uri=" in auth_url
        assert "response_type=code" in auth_url
        assert "scope=" in auth_url
        assert f"state={state}" in auth_url
        assert len(state) > 0

    def test_generate_authorization_url_with_custom_state(self, google_config):
        """Test authorization URL with custom state."""
        provider = GoogleOAuth2Provider(google_config)
        custom_state = "custom-state-value"
        auth_url, state = provider.generate_authorization_url(custom_state)

        assert state == custom_state
        assert f"state={custom_state}" in auth_url

    @pytest.mark.asyncio
    async def test_extract_user_from_token(self, google_config):
        """Test extracting user from Google token."""
        provider = GoogleOAuth2Provider(google_config)

        # Mock validate_id_token
        with patch.object(provider, "validate_id_token", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "email": "test@gmail.com",
                "name": "Test User",
                "sub": "google-user-id",
            }

            token_data = {"id_token": "mock-id-token"}
            user = await provider.extract_user_from_token(token_data)

            assert isinstance(user, User)
            assert user.username == "test@gmail.com"
            assert user.email == "test@gmail.com"
            assert user.full_name == "Test User"

    @pytest.mark.asyncio
    async def test_extract_user_no_id_token(self, google_config):
        """Test extracting user without ID token raises error."""
        provider = GoogleOAuth2Provider(google_config)

        token_data = {"access_token": "mock-access-token"}

        with pytest.raises(Exception, match="No ID token in response"):
            await provider.extract_user_from_token(token_data)


class TestAzureADOAuth2Provider:
    """Test Azure AD OAuth2 provider."""

    def test_provider_name(self, azure_config):
        """Test provider name."""
        provider = AzureADOAuth2Provider(azure_config)
        assert provider.get_provider_name() == "azure"

    def test_generate_authorization_url(self, azure_config):
        """Test authorization URL generation."""
        provider = AzureADOAuth2Provider(azure_config)
        auth_url, _state = provider.generate_authorization_url()

        assert "login.microsoftonline.com" in auth_url
        assert "test-tenant" in auth_url
        assert "client_id=azure-client-id" in auth_url

    @pytest.mark.asyncio
    async def test_extract_user_from_token(self, azure_config):
        """Test extracting user from Azure AD token."""
        provider = AzureADOAuth2Provider(azure_config)

        with patch.object(provider, "validate_id_token", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "preferred_username": "test@company.com",
                "email": "test@company.com",
                "name": "Test User",
                "sub": "azure-user-id",
            }

            token_data = {"id_token": "mock-id-token"}
            user = await provider.extract_user_from_token(token_data)

            assert isinstance(user, User)
            assert user.username == "test@company.com"
            assert user.email == "test@company.com"
            assert user.full_name == "Test User"

    @pytest.mark.asyncio
    async def test_extract_user_fallback_to_email(self, azure_config):
        """Test extracting user falls back to email if no preferred_username."""
        provider = AzureADOAuth2Provider(azure_config)

        with patch.object(provider, "validate_id_token", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "email": "test@company.com",
                "name": "Test User",
            }

            token_data = {"id_token": "mock-id-token"}
            user = await provider.extract_user_from_token(token_data)

            assert user.username == "test@company.com"


class TestGenericOIDCProvider:
    """Test Generic OIDC provider."""

    def test_provider_name(self, oauth2_config):
        """Test provider name."""
        provider = GenericOIDCProvider(oauth2_config)
        assert provider.get_provider_name() == "generic"

    @pytest.mark.asyncio
    async def test_extract_user_from_id_token(self, oauth2_config):
        """Test extracting user from ID token."""
        provider = GenericOIDCProvider(oauth2_config)

        with patch.object(provider, "validate_id_token", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "preferred_username": "testuser",
                "email": "test@example.com",
                "name": "Test User",
                "sub": "user-id",
            }

            token_data = {"id_token": "mock-id-token"}
            user = await provider.extract_user_from_token(token_data)

            assert user.username == "testuser"
            assert user.email == "test@example.com"
            assert user.full_name == "Test User"

    @pytest.mark.asyncio
    async def test_extract_user_from_access_token(self, oauth2_config):
        """Test extracting user from access token via userinfo."""
        provider = GenericOIDCProvider(oauth2_config)

        with patch.object(provider, "get_user_info", new_callable=AsyncMock) as mock_userinfo:
            mock_userinfo.return_value = {
                "email": "test@example.com",
                "name": "Test User",
                "sub": "user-id",
            }

            token_data = {"access_token": "mock-access-token"}
            user = await provider.extract_user_from_token(token_data)

            assert user.username == "test@example.com"
            assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_extract_user_username_fallback(self, oauth2_config):
        """Test username fallback logic."""
        provider = GenericOIDCProvider(oauth2_config)

        with patch.object(provider, "validate_id_token", new_callable=AsyncMock) as mock_validate:
            # Test fallback: preferred_username -> email -> sub
            mock_validate.return_value = {
                "sub": "user-id-123",
                "name": "Test User",
            }

            token_data = {"id_token": "mock-id-token"}
            user = await provider.extract_user_from_token(token_data)

            assert user.username == "user-id-123"

    @pytest.mark.asyncio
    async def test_extract_user_no_token(self, oauth2_config):
        """Test extracting user without any token raises error."""
        provider = GenericOIDCProvider(oauth2_config)

        token_data: dict[str, str] = {}

        with pytest.raises(Exception, match="No ID token or access token in response"):
            await provider.extract_user_from_token(token_data)


class TestOAuth2ProviderCommon:
    """Test common OAuth2 provider functionality."""

    @pytest.mark.asyncio
    async def test_exchange_code_for_token(self, oauth2_config):
        """Test exchanging authorization code for token."""
        provider = GenericOIDCProvider(oauth2_config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "mock-access-token",
            "id_token": "mock-id-token",
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            token_data = await provider.exchange_code_for_token("auth-code")

            assert token_data["access_token"] == "mock-access-token"
            assert token_data["id_token"] == "mock-id-token"

    @pytest.mark.asyncio
    async def test_discover_endpoints(self, oauth2_config):
        """Test OIDC discovery."""
        oauth2_config.oauth2_discovery_url = "https://provider.com/.well-known/openid-configuration"
        provider = GenericOIDCProvider(oauth2_config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "issuer": "https://provider.com",
            "authorization_endpoint": "https://provider.com/authorize",
            "token_endpoint": "https://provider.com/token",
            "jwks_uri": "https://provider.com/jwks",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            discovery = await provider.discover_endpoints()

            assert discovery["issuer"] == "https://provider.com"
            assert discovery["authorization_endpoint"] == "https://provider.com/authorize"

    @pytest.mark.asyncio
    async def test_discover_endpoints_cached(self, oauth2_config):
        """Test that discovery results are cached."""
        from datetime import UTC, datetime

        oauth2_config.oauth2_discovery_url = "https://provider.com/.well-known/openid-configuration"
        provider = GenericOIDCProvider(oauth2_config)

        # Set cache with a fresh timestamp so TTL guard passes
        provider._discovery_cache = {"cached": "data"}
        provider._discovery_cache_time = datetime.now(UTC)

        # Should return cached data without making HTTP request
        discovery = await provider.discover_endpoints()

        assert discovery == {"cached": "data"}


class TestGetOAuth2Provider:
    """Test OAuth2 provider factory function."""

    def test_get_google_provider(self, google_config):
        """Test getting Google provider."""
        provider = get_oauth2_provider(google_config)

        assert isinstance(provider, GoogleOAuth2Provider)
        assert provider.get_provider_name() == "google"

    def test_get_azure_provider(self, azure_config):
        """Test getting Azure provider."""
        provider = get_oauth2_provider(azure_config)

        assert isinstance(provider, AzureADOAuth2Provider)
        assert provider.get_provider_name() == "azure"

    def test_get_generic_provider(self, oauth2_config):
        """Test getting generic provider."""
        provider = get_oauth2_provider(oauth2_config)

        assert isinstance(provider, GenericOIDCProvider)
        assert provider.get_provider_name() == "generic"

    def test_get_provider_unknown(self):
        """Test getting provider with unknown type."""
        config = OAuth2Config(oauth2_provider="unknown")
        provider = get_oauth2_provider(config)

        assert isinstance(provider, GenericOIDCProvider)
