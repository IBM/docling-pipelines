"""JWT token handling module."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class JWTConfig(BaseSettings):
    """JWT configuration settings."""

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


def create_access_token(data: dict, config: JWTConfig) -> str:
    """Generate JWT access token.

    Args:
        data: Data to encode in the token
        config: JWT configuration

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=config.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})

    try:
        encoded_jwt = jwt.encode(to_encode, config.jwt_secret_key, algorithm=config.jwt_algorithm)
        logger.info(f"Created access token for user: {data.get('username', 'unknown')}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {e!s}")
        raise


def verify_token(token: str, config: JWTConfig) -> dict | None:
    """Verify and decode JWT token.

    Args:
        token: JWT token string
        config: JWT configuration

    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload: dict[str, Any] = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
        username: Any | None = payload.get("username")
        if username is None:
            logger.warning("Token missing username claim")
            return None
        logger.debug(f"Token verified for user: {username}")
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e!s}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error verifying token: {e!s}")
        return None
