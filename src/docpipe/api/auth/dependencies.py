"""FastAPI dependencies for authentication."""

import logging
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2AuthorizationCodeBearer

from .jwt_handler import JWTConfig, verify_token
from .models import User

logger = logging.getLogger(__name__)

security = HTTPBearer()

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="/auth/oauth2/authorize",
    tokenUrl="/auth/oauth2/callback",
    auto_error=False,
)


def get_jwt_config() -> JWTConfig:
    """Get JWT configuration.

    Returns:
        JWT configuration instance
    """
    return JWTConfig()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    jwt_config: Annotated[JWTConfig, Depends(get_jwt_config)],
) -> User:
    """FastAPI dependency to extract and validate current user from JWT.

    Args:
        credentials: HTTP authorization credentials
        jwt_config: JWT configuration

    Returns:
        User object from token payload

    Raises:
        HTTPException: If token is invalid or missing required claims
    """
    token = credentials.credentials
    payload: dict[Any, Any] | None = verify_token(token, jwt_config)

    if payload is None:
        logger.warning("Invalid authentication token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("username")
    if username is None:
        logger.warning("Token missing username claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = User(
        username=username,
        email=payload.get("email", ""),
        full_name=payload.get("full_name", ""),
    )

    logger.debug(f"Authenticated user: {username}")
    return user


async def get_current_user_oauth2(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    jwt_config: Annotated[JWTConfig, Depends(get_jwt_config)],
) -> User | None:
    """FastAPI dependency to extract user from OAuth2 token.

    Args:
        token: OAuth2 token from authorization header
        jwt_config: JWT configuration

    Returns:
        User object if token is valid, None otherwise
    """
    if not token:
        return None

    payload: dict[Any, Any] | None = verify_token(token, jwt_config)

    if payload is None:
        return None

    username = payload.get("username")
    if username is None:
        return None

    return User(
        username=username,
        email=payload.get("email", ""),
        full_name=payload.get("full_name", ""),
    )


async def get_current_user_flexible(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    oauth2_token: Annotated[str | None, Depends(oauth2_scheme)],
    jwt_config: Annotated[JWTConfig, Depends(get_jwt_config)],
) -> User:
    """FastAPI dependency supporting both Bearer token and OAuth2.

    Args:
        credentials: HTTP authorization credentials (Bearer token)
        oauth2_token: OAuth2 token
        jwt_config: JWT configuration

    Returns:
        User object from token payload

    Raises:
        HTTPException: If no valid token provided
    """
    if credentials:
        token = credentials.credentials
        payload: dict[Any, Any] | None = verify_token(token, jwt_config)

        if payload is not None:
            username = payload.get("username")
            if username is not None:
                return User(
                    username=username,
                    email=payload.get("email", ""),
                    full_name=payload.get("full_name", ""),
                )

    if oauth2_token:
        payload = verify_token(oauth2_token, jwt_config)

        if payload is not None:
            username = payload.get("username")
            if username is not None:
                return User(
                    username=username,
                    email=payload.get("email", ""),
                    full_name=payload.get("full_name", ""),
                )

    logger.warning("No valid authentication token provided")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
