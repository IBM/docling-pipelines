"""OAuth2 provider implementation with OIDC support."""

import logging
import secrets
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from .models import User
from .oauth2_config import OAuth2Config

logger = logging.getLogger(__name__)


class OAuth2Provider(ABC):
    """Base OAuth2 provider class."""

    def __init__(self, config: OAuth2Config):
        """Initialize OAuth2 provider.

        Args:
            config: OAuth2 configuration
        """
        self.config = config
        self._discovery_cache: dict[str, Any] | None = None
        self._jwks_cache: dict[str, Any] | None = None

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            Provider name string
        """
        pass

    async def discover_endpoints(self) -> dict[str, Any]:
        """Discover OAuth2/OIDC endpoints via discovery document.

        Returns:
            Dictionary containing discovered endpoints

        Raises:
            Exception: If discovery fails
        """
        if self._discovery_cache is not None:
            return self._discovery_cache

        if not self.config.oauth2_discovery_url:
            logger.warning(f"No discovery URL configured for {self.get_provider_name()}")
            self._discovery_cache = {}
            return self._discovery_cache

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.config.oauth2_discovery_url, timeout=10.0)
                response.raise_for_status()
                self._discovery_cache = response.json()
                logger.info(f"Successfully discovered endpoints for {self.get_provider_name()}")
                return self._discovery_cache
        except Exception as e:
            logger.error(f"Failed to discover endpoints for {self.get_provider_name()}: {e!s}")
            raise Exception(f"OIDC discovery failed: {e!s}") from e

    async def get_jwks(self) -> dict[str, Any]:
        """Fetch JWKS (JSON Web Key Set) for token validation.

        Returns:
            JWKS dictionary

        Raises:
            Exception: If JWKS fetch fails
        """
        if self._jwks_cache is not None:
            return self._jwks_cache

        jwks_uri = self.config.oauth2_jwks_uri
        if not jwks_uri:
            discovery = await self.discover_endpoints()
            jwks_uri = discovery.get("jwks_uri", "")

        if not jwks_uri:
            raise Exception("JWKS URI not configured or discovered")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_uri, timeout=10.0)
                response.raise_for_status()
                self._jwks_cache = response.json()
                logger.info(f"Successfully fetched JWKS for {self.get_provider_name()}")
                return self._jwks_cache
        except Exception as e:
            logger.error(f"Failed to fetch JWKS for {self.get_provider_name()}: {e!s}")
            raise Exception(f"JWKS fetch failed: {e!s}") from e

    def generate_authorization_url(self, state: str | None = None) -> tuple[str, str]:
        """Generate OAuth2 authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        if not state:
            state = secrets.token_urlsafe(32)

        auth_endpoint = self.config.oauth2_authorization_endpoint

        params = {
            "client_id": self.config.oauth2_client_id,
            "redirect_uri": self.config.oauth2_redirect_uri,
            "response_type": "code",
            "scope": self.config.oauth2_scope,
            "state": state,
        }

        authorization_url = f"{auth_endpoint}?{urlencode(params)}"
        logger.debug(f"Generated authorization URL for {self.get_provider_name()}")
        return authorization_url, state

    async def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth2 callback

        Returns:
            Token response dictionary

        Raises:
            Exception: If token exchange fails
        """
        token_endpoint = self.config.oauth2_token_endpoint

        data = {
            "client_id": self.config.oauth2_client_id,
            "client_secret": self.config.oauth2_client_secret,
            "code": code,
            "redirect_uri": self.config.oauth2_redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_endpoint, data=data, timeout=10.0)
                response.raise_for_status()
                token_data = response.json()
                logger.info(f"Successfully exchanged code for token with {self.get_provider_name()}")
                return token_data
        except Exception as e:
            logger.error(f"Failed to exchange code for token with {self.get_provider_name()}: {e!s}")
            raise Exception(f"Token exchange failed: {e!s}") from e

    async def validate_id_token(self, id_token: str) -> dict[str, Any]:
        """Validate OIDC ID token.

        Args:
            id_token: ID token to validate

        Returns:
            Decoded token payload

        Raises:
            Exception: If token validation fails
        """
        try:
            jwks = await self.get_jwks()

            unverified_header = jwt.get_unverified_header(id_token)
            kid = unverified_header.get("kid")

            key = None
            for jwk in jwks.get("keys", []):
                if jwk.get("kid") == kid:
                    key = jwk
                    break

            if not key:
                raise Exception(f"No matching key found for kid: {kid}")

            payload = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=self.config.oidc_audience or self.config.oauth2_client_id,
                issuer=self.config.oidc_issuer,
            )

            logger.info(f"Successfully validated ID token for {self.get_provider_name()}")
            return payload

        except JWTError as e:
            logger.error(f"JWT validation failed for {self.get_provider_name()}: {e!s}")
            raise Exception(f"ID token validation failed: {e!s}") from e
        except Exception as e:
            logger.error(f"Token validation error for {self.get_provider_name()}: {e!s}")
            raise Exception(f"Token validation failed: {e!s}") from e

    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        """Fetch user information from userinfo endpoint.

        Args:
            access_token: OAuth2 access token

        Returns:
            User information dictionary

        Raises:
            Exception: If userinfo fetch fails
        """
        userinfo_endpoint = self.config.oauth2_userinfo_endpoint

        if not userinfo_endpoint:
            discovery = await self.discover_endpoints()
            userinfo_endpoint = discovery.get("userinfo_endpoint", "")

        if not userinfo_endpoint:
            raise Exception("Userinfo endpoint not configured or discovered")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0,
                )
                response.raise_for_status()
                userinfo = response.json()
                logger.info(f"Successfully fetched user info from {self.get_provider_name()}")
                return userinfo
        except Exception as e:
            logger.error(f"Failed to fetch user info from {self.get_provider_name()}: {e!s}")
            raise Exception(f"Userinfo fetch failed: {e!s}") from e

    @abstractmethod
    async def extract_user_from_token(self, token_data: dict[str, Any]) -> User:
        """Extract user information from token data.

        Args:
            token_data: Token response data

        Returns:
            User object
        """
        pass


class GoogleOAuth2Provider(OAuth2Provider):
    """Google OAuth2 provider implementation."""

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "google"

    async def extract_user_from_token(self, token_data: dict[str, Any]) -> User:
        """Extract user from Google token data."""
        id_token = token_data.get("id_token")
        if not id_token:
            raise Exception("No ID token in response")

        payload = await self.validate_id_token(id_token)

        return User(
            username=payload.get("email", ""),
            email=payload.get("email", ""),
            full_name=payload.get("name", ""),
        )


class AzureADOAuth2Provider(OAuth2Provider):
    """Azure AD OAuth2 provider implementation."""

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "azure"

    async def extract_user_from_token(self, token_data: dict[str, Any]) -> User:
        """Extract user from Azure AD token data."""
        id_token = token_data.get("id_token")
        if not id_token:
            raise Exception("No ID token in response")

        payload = await self.validate_id_token(id_token)

        return User(
            username=payload.get("preferred_username", payload.get("email", "")),
            email=payload.get("email", payload.get("preferred_username", "")),
            full_name=payload.get("name", ""),
        )


class GenericOIDCProvider(OAuth2Provider):
    """Generic OIDC provider implementation."""

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "generic"

    async def extract_user_from_token(self, token_data: dict[str, Any]) -> User:
        """Extract user from generic OIDC token data."""
        id_token = token_data.get("id_token")
        access_token = token_data.get("access_token")

        if id_token:
            payload = await self.validate_id_token(id_token)
        elif access_token:
            payload = await self.get_user_info(access_token)
        else:
            raise Exception("No ID token or access token in response")

        username = payload.get("preferred_username") or payload.get("email") or payload.get("sub") or ""
        email = payload.get("email", "")
        full_name = payload.get("name", "")

        return User(
            username=username,
            email=email,
            full_name=full_name,
        )


def get_oauth2_provider(config: OAuth2Config) -> OAuth2Provider:
    """Get OAuth2 provider instance based on configuration.

    Args:
        config: OAuth2 configuration

    Returns:
        OAuth2Provider instance
    """
    provider_name = config.oauth2_provider.lower()

    if provider_name == "google":
        return GoogleOAuth2Provider(config)
    elif provider_name == "azure":
        return AzureADOAuth2Provider(config)
    else:
        return GenericOIDCProvider(config)
