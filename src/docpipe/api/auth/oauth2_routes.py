"""OAuth2 authentication routes."""

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import RedirectResponse

from .jwt_handler import JWTConfig, create_access_token
from .models import TokenResponse
from .oauth2_config import OAuth2Config, get_oauth2_config
from .oauth2_provider import OAuth2Provider, get_oauth2_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/oauth2", tags=["oauth2"])

_state_store: dict[str, str] = {}


def get_oauth2_provider_instance(
    provider: str | None = Query(None, description="OAuth2 provider (google, azure, generic)"),
) -> OAuth2Provider:
    """Get OAuth2 provider instance.

    Args:
        provider: OAuth2 provider name

    Returns:
        OAuth2Provider instance

    Raises:
        HTTPException: If OAuth2 is not enabled or configured
    """
    config = get_oauth2_config(provider)

    if not config.oauth2_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth2 authentication is not enabled",
        )

    if not config.oauth2_client_id or not config.oauth2_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth2 is not properly configured",
        )

    return get_oauth2_provider(config)


@router.get("/authorize")
async def oauth2_authorize(
    provider_instance: Annotated[OAuth2Provider, Depends(get_oauth2_provider_instance)],
    redirect_after: str | None = Query(None, description="URL to redirect after successful login"),
):
    """Initiate OAuth2 authorization flow.

    Args:
        provider_instance: OAuth2 provider instance
        redirect_after: Optional URL to redirect after login

    Returns:
        Redirect to OAuth2 provider authorization page
    """
    try:
        state = secrets.token_urlsafe(32)
        _state_store[state] = redirect_after or ""
        auth_url, _ = provider_instance.generate_authorization_url(state)

        logger.info(f"Initiating OAuth2 flow with {provider_instance.get_provider_name()}")
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"Failed to initiate OAuth2 flow: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate OAuth2 flow: {e!s}",
        ) from e


@router.get("/callback")
async def oauth2_callback(
    request: Request,
    provider_instance: Annotated[OAuth2Provider, Depends(get_oauth2_provider_instance)],
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
):
    """Handle OAuth2 callback and exchange code for token.

    Args:
        request: FastAPI request object
        provider_instance: OAuth2 provider instance
        code: Authorization code from OAuth2 provider
        state: State parameter for CSRF validation

    Returns:
        Redirect with access token or token response
    """
    try:
        if state not in _state_store:
            logger.warning("Invalid OAuth2 state parameter received")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter",
            )

        redirect_after = _state_store.pop(state)

        token_data = await provider_instance.exchange_code_for_token(code)
        user = await provider_instance.extract_user_from_token(token_data)

        try:
            jwt_config = JWTConfig()
        except Exception as e:
            logger.error(f"Failed to load JWT config: {e!s}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="JWT configuration not available",
            ) from e

        jwt_token_data = {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
        }
        access_token = create_access_token(jwt_token_data, jwt_config)

        logger.info(f"OAuth2 login successful for user: {user.username}")

        if redirect_after:
            redirect_url = f"{redirect_after}?access_token={access_token}"
            return RedirectResponse(url=redirect_url)

        return TokenResponse(access_token=access_token)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth2 callback error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth2 authentication failed: {e!s}",
        ) from e


@router.get("/providers")
async def list_oauth2_providers():
    """List available OAuth2 providers.

    Returns:
        List of configured OAuth2 providers
    """
    providers = []

    for provider_name in ["google", "azure", "generic"]:
        try:
            config = get_oauth2_config(provider_name)
            if config.oauth2_enabled and config.oauth2_client_id:
                providers.append(
                    {
                        "name": provider_name,
                        "display_name": provider_name.title(),
                        "authorize_url": f"/auth/oauth2/authorize?provider={provider_name}",
                    }
                )
        except Exception:
            continue

    return {"providers": providers}


@router.get("/discovery/{provider}")
async def oauth2_discovery(
    provider: Annotated[str, Path(description="OAuth2 provider name")],
    config: Annotated[OAuth2Config, Depends(get_oauth2_config)],
):
    """Get OAuth2/OIDC discovery information for a provider.

    Args:
        provider: Provider name
        config: OAuth2 configuration

    Returns:
        Discovery document
    """
    try:
        provider_instance = get_oauth2_provider(config)
        discovery = await provider_instance.discover_endpoints()
        return discovery
    except Exception as e:
        logger.error(f"Failed to fetch discovery document: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch discovery document: {e!s}",
        ) from e
