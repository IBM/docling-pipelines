"""Unit tests for JWT token handling."""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from docpipe.api.auth.jwt_handler import (
    JWTConfig,
    create_access_token,
    verify_token,
)


@pytest.fixture
def jwt_config():
    """Create JWT configuration for testing."""
    return JWTConfig(
        jwt_secret_key="test-secret-key-for-testing-only",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
    )


class TestJWTConfig:
    """Test JWT configuration."""

    def test_jwt_config_defaults(self):
        """Test JWT config with default values."""
        config = JWTConfig(jwt_secret_key="test-key")
        assert config.jwt_algorithm == "HS256"
        assert config.jwt_access_token_expire_minutes == 30

    def test_jwt_config_custom_values(self):
        """Test JWT config with custom values."""
        config = JWTConfig(
            jwt_secret_key="custom-key",
            jwt_algorithm="HS512",
            jwt_access_token_expire_minutes=60,
        )
        assert config.jwt_secret_key == "custom-key"
        assert config.jwt_algorithm == "HS512"
        assert config.jwt_access_token_expire_minutes == 60


class TestCreateAccessToken:
    """Test access token creation."""

    def test_create_token_with_user_data(self, jwt_config):
        """Test creating token with user data."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
        }

        token = create_access_token(data, jwt_config)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_expiration(self, jwt_config):
        """Test that token contains expiration claim."""
        data = {"username": "testuser"}
        token = create_access_token(data, jwt_config)

        # Decode without verification to check claims
        payload = jwt.decode(
            token,
            jwt_config.jwt_secret_key,
            algorithms=[jwt_config.jwt_algorithm],
        )

        assert "exp" in payload
        assert "username" in payload
        assert payload["username"] == "testuser"

    def test_token_expiration_time(self, jwt_config):
        """Test that token expiration is set correctly."""
        data = {"username": "testuser"}
        before_creation = datetime.now(UTC)
        token = create_access_token(data, jwt_config)
        after_creation = datetime.now(UTC)

        payload = jwt.decode(
            token,
            jwt_config.jwt_secret_key,
            algorithms=[jwt_config.jwt_algorithm],
        )

        datetime.fromtimestamp(payload["exp"], tz=UTC)
        expected_min = before_creation + timedelta(minutes=jwt_config.jwt_access_token_expire_minutes)
        expected_max = after_creation + timedelta(minutes=jwt_config.jwt_access_token_expire_minutes)

        assert expected_min <= expected_max

    def test_token_preserves_data(self, jwt_config):
        """Test that token preserves all provided data."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "custom_field": "custom_value",
        }

        token = create_access_token(data, jwt_config)
        payload = jwt.decode(
            token,
            jwt_config.jwt_secret_key,
            algorithms=[jwt_config.jwt_algorithm],
        )

        assert payload["username"] == data["username"]
        assert payload["email"] == data["email"]
        assert payload["full_name"] == data["full_name"]
        assert payload["custom_field"] == data["custom_field"]


class TestVerifyToken:
    """Test token verification."""

    def test_verify_valid_token(self, jwt_config):
        """Test verifying a valid token."""
        data = {"username": "testuser", "email": "test@example.com"}
        token = create_access_token(data, jwt_config)

        payload = verify_token(token, jwt_config)

        assert payload is not None
        assert payload["username"] == "testuser"
        assert payload["email"] == "test@example.com"

    def test_verify_token_without_username(self, jwt_config):
        """Test verifying token without username claim."""
        data = {"email": "test@example.com"}
        token = create_access_token(data, jwt_config)

        payload = verify_token(token, jwt_config)

        assert payload is None

    def test_verify_expired_token(self, jwt_config):
        """Test verifying an expired token."""
        data = {"username": "testuser"}
        # Create token with past expiration
        to_encode = data.copy()
        expire = datetime.now(UTC) - timedelta(minutes=1)
        to_encode.update({"exp": expire})

        token = jwt.encode(
            to_encode,
            jwt_config.jwt_secret_key,
            algorithm=jwt_config.jwt_algorithm,
        )

        payload = verify_token(token, jwt_config)

        assert payload is None

    def test_verify_token_wrong_secret(self, jwt_config):
        """Test verifying token with wrong secret."""
        data = {"username": "testuser"}
        token = create_access_token(data, jwt_config)

        # Create config with different secret
        wrong_config = JWTConfig(
            jwt_secret_key="wrong-secret-key",
            jwt_algorithm="HS256",
        )

        payload = verify_token(token, wrong_config)

        assert payload is None

    def test_verify_malformed_token(self, jwt_config):
        """Test verifying a malformed token."""
        malformed_token = "not.a.valid.jwt.token"

        payload = verify_token(malformed_token, jwt_config)

        assert payload is None

    def test_verify_token_wrong_algorithm(self, jwt_config):
        """Test verifying token with wrong algorithm."""
        data = {"username": "testuser"}
        # Create token with HS512
        token = jwt.encode(
            data,
            jwt_config.jwt_secret_key,
            algorithm="HS512",
        )

        payload = verify_token(token, jwt_config)

        assert payload is None

    def test_verify_empty_token(self, jwt_config):
        """Test verifying an empty token."""
        payload = verify_token("", jwt_config)

        assert payload is None
