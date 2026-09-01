"""Unit tests for JWT handler module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from jose import JWTError, jwt

from docpipe.api.auth.jwt_handler import (
    JWTClaims,
    JWTConfig,
    create_access_token,
    verify_token,
)


# ---------------------------------------------------------------------------
# JWTConfig validation tests
# ---------------------------------------------------------------------------


def test_jwt_config_accepts_valid_secret():
    """Test that JWTConfig accepts a secret key meeting minimum length."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    assert config.jwt_secret_key == "a" * 32


def test_jwt_config_rejects_short_secret():
    """Test that JWTConfig rejects secret keys shorter than minimum length."""
    with pytest.raises(ValueError, match="at least 32 characters"):
        JWTConfig(jwt_secret_key="short")


def test_jwt_config_rejects_empty_secret():
    """Test that JWTConfig rejects empty secret key."""
    with pytest.raises(ValueError, match="at least 32 characters"):
        JWTConfig(jwt_secret_key="")


def test_jwt_config_default_algorithm():
    """Test that JWTConfig uses HS256 as default algorithm."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    assert config.jwt_algorithm == "HS256"


def test_jwt_config_custom_algorithm():
    """Test that JWTConfig accepts custom algorithm."""
    config = JWTConfig(jwt_secret_key="a" * 32, jwt_algorithm="HS512")
    assert config.jwt_algorithm == "HS512"


def test_jwt_config_default_expiration():
    """Test that JWTConfig uses 30 minutes as default expiration."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    assert config.jwt_access_token_expire_minutes == 30


def test_jwt_config_custom_expiration():
    """Test that JWTConfig accepts custom expiration time."""
    config = JWTConfig(jwt_secret_key="a" * 32, jwt_access_token_expire_minutes=60)
    assert config.jwt_access_token_expire_minutes == 60


# ---------------------------------------------------------------------------
# create_access_token tests
# ---------------------------------------------------------------------------


def test_create_access_token_returns_string():
    """Test that create_access_token returns a string token."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    token = create_access_token({"username": "testuser"}, config)
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_includes_username():
    """Test that created token includes username claim."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    token = create_access_token({"username": "testuser"}, config)
    
    decoded = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
    assert decoded["username"] == "testuser"


def test_create_access_token_includes_email():
    """Test that created token includes email claim."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    token = create_access_token({"username": "testuser", "email": "test@example.com"}, config)
    
    decoded = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
    assert decoded["email"] == "test@example.com"


def test_create_access_token_includes_full_name():
    """Test that created token includes full_name claim."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    token = create_access_token(
        {"username": "testuser", "full_name": "Test User"}, 
        config
    )
    
    decoded = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
    assert decoded["full_name"] == "Test User"


def test_create_access_token_adds_expiration():
    """Test that created token includes expiration claim."""
    config = JWTConfig(jwt_secret_key="a" * 32, jwt_access_token_expire_minutes=30)
    before = datetime.now(UTC)
    token = create_access_token({"username": "testuser"}, config)
    after = datetime.now(UTC)
    
    decoded = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
    exp_time = datetime.fromtimestamp(decoded["exp"], UTC)
    
    # Expiration should be approximately 30 minutes from now
    expected_min = before + timedelta(minutes=29, seconds=50)
    expected_max = after + timedelta(minutes=30, seconds=10)
    assert expected_min <= exp_time <= expected_max


def test_create_access_token_respects_custom_expiration():
    """Test that created token respects custom expiration time."""
    config = JWTConfig(jwt_secret_key="a" * 32, jwt_access_token_expire_minutes=60)
    before = datetime.now(UTC)
    token = create_access_token({"username": "testuser"}, config)
    after = datetime.now(UTC)
    
    decoded = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
    exp_time = datetime.fromtimestamp(decoded["exp"], UTC)
    
    # Expiration should be approximately 60 minutes from now
    expected_min = before + timedelta(minutes=59, seconds=50)
    expected_max = after + timedelta(minutes=60, seconds=10)
    assert expected_min <= exp_time <= expected_max


def test_create_access_token_preserves_custom_claims():
    """Test that created token preserves custom claims."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    token = create_access_token(
        {"username": "testuser", "custom_field": "custom_value"}, 
        config
    )
    
    decoded = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
    assert decoded["custom_field"] == "custom_value"


def test_create_access_token_does_not_modify_input():
    """Test that create_access_token does not modify input data dict."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    data = {"username": "testuser"}
    original_keys = set(data.keys())
    
    create_access_token(data, config)
    
    assert set(data.keys()) == original_keys
    assert "exp" not in data


def test_create_access_token_with_empty_data():
    """Test that create_access_token works with empty data dict."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    token = create_access_token({}, config)
    
    decoded = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
    assert "exp" in decoded


def test_create_access_token_logs_username(caplog):
    """Test that create_access_token logs the username."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    with caplog.at_level("INFO"):
        create_access_token({"username": "testuser"}, config)
    
    assert "testuser" in caplog.text
    assert "Created access token" in caplog.text


def test_create_access_token_logs_unknown_for_missing_username(caplog):
    """Test that create_access_token logs 'unknown' when username is missing."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    with caplog.at_level("INFO"):
        create_access_token({"email": "test@example.com"}, config)
    
    assert "unknown" in caplog.text


def test_create_access_token_raises_on_encoding_error():
    """Test that create_access_token raises exception on encoding error."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    with patch("docpipe.api.auth.jwt_handler.jwt.encode", side_effect=Exception("encoding failed")):
        with pytest.raises(Exception, match="encoding failed"):
            create_access_token({"username": "testuser"}, config)


# ---------------------------------------------------------------------------
# verify_token tests
# ---------------------------------------------------------------------------


def test_verify_token_returns_payload_for_valid_token():
    """Test that verify_token returns payload for valid token."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    token = create_access_token({"username": "testuser", "email": "test@example.com"}, config)
    
    payload = verify_token(token, config)
    
    assert payload is not None
    assert payload["username"] == "testuser"
    assert payload["email"] == "test@example.com"


def test_verify_token_returns_none_for_invalid_signature():
    """Test that verify_token returns None for token with invalid signature."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    token = create_access_token({"username": "testuser"}, config)
    
    # Use different secret to verify
    wrong_config = JWTConfig(jwt_secret_key="b" * 32)
    payload = verify_token(token, wrong_config)
    
    assert payload is None


def test_verify_token_returns_none_for_expired_token():
    """Test that verify_token returns None for expired token."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    # Create token that expired 1 minute ago
    data = {"username": "testuser"}
    expire = datetime.now(UTC) - timedelta(minutes=1)
    data.update({"exp": expire})
    token = jwt.encode(data, config.jwt_secret_key, algorithm=config.jwt_algorithm)
    
    payload = verify_token(token, config)
    
    assert payload is None


def test_verify_token_returns_none_for_malformed_token():
    """Test that verify_token returns None for malformed token."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    payload = verify_token("not.a.valid.token", config)
    
    assert payload is None


def test_verify_token_returns_none_for_token_without_username():
    """Test that verify_token returns None when token lacks username claim."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    # Create token without username
    data = {"email": "test@example.com"}
    expire = datetime.now(UTC) + timedelta(minutes=30)
    data.update({"exp": expire})
    token = jwt.encode(data, config.jwt_secret_key, algorithm=config.jwt_algorithm)
    
    payload = verify_token(token, config)
    
    assert payload is None


def test_verify_token_logs_warning_for_missing_username(caplog):
    """Test that verify_token logs warning when username claim is missing."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    data = {"email": "test@example.com"}
    expire = datetime.now(UTC) + timedelta(minutes=30)
    data.update({"exp": expire})
    token = jwt.encode(data, config.jwt_secret_key, algorithm=config.jwt_algorithm)
    
    with caplog.at_level("WARNING"):
        verify_token(token, config)
    
    assert "Token missing username claim" in caplog.text


def test_verify_token_logs_warning_for_jwt_error(caplog):
    """Test that verify_token logs warning for JWT verification failure."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    with caplog.at_level("WARNING"):
        verify_token("invalid.token.here", config)
    
    assert "JWT verification failed" in caplog.text


def test_verify_token_logs_debug_for_valid_token(caplog):
    """Test that verify_token logs debug message for valid token."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    token = create_access_token({"username": "testuser"}, config)
    
    with caplog.at_level("DEBUG"):
        verify_token(token, config)
    
    assert "Token verified for user: testuser" in caplog.text


def test_verify_token_handles_unexpected_exception():
    """Test that verify_token handles unexpected exceptions gracefully."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    with patch("docpipe.api.auth.jwt_handler.jwt.decode", side_effect=Exception("unexpected error")):
        payload = verify_token("some-token", config)
    
    assert payload is None


def test_verify_token_logs_error_for_unexpected_exception(caplog):
    """Test that verify_token logs error for unexpected exceptions."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    with patch("docpipe.api.auth.jwt_handler.jwt.decode", side_effect=Exception("unexpected error")):
        with caplog.at_level("ERROR"):
            verify_token("some-token", config)
    
    assert "Unexpected error verifying token" in caplog.text


def test_verify_token_with_different_algorithm():
    """Test that verify_token works with different algorithm."""
    config = JWTConfig(jwt_secret_key="a" * 32, jwt_algorithm="HS512")
    token = create_access_token({"username": "testuser"}, config)
    
    payload = verify_token(token, config)
    
    assert payload is not None
    assert payload["username"] == "testuser"


def test_verify_token_rejects_token_with_wrong_algorithm():
    """Test that verify_token rejects token signed with different algorithm."""
    config_hs256 = JWTConfig(jwt_secret_key="a" * 32, jwt_algorithm="HS256")
    config_hs512 = JWTConfig(jwt_secret_key="a" * 32, jwt_algorithm="HS512")
    
    token = create_access_token({"username": "testuser"}, config_hs256)
    
    # Try to verify with HS512
    payload = verify_token(token, config_hs512)
    
    assert payload is None


# ---------------------------------------------------------------------------
# JWTClaims constant tests
# ---------------------------------------------------------------------------


def test_jwt_claims_constants():
    """Test that JWTClaims constants have expected values."""
    assert JWTClaims.USERNAME == "username"
    assert JWTClaims.EMAIL == "email"
    assert JWTClaims.FULL_NAME == "full_name"


# ---------------------------------------------------------------------------
# Integration-style tests
# ---------------------------------------------------------------------------


def test_create_and_verify_token_roundtrip():
    """Test creating and verifying token in a roundtrip."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    original_data = {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
    }
    
    token = create_access_token(original_data, config)
    payload = verify_token(token, config)
    
    assert payload is not None
    assert payload["username"] == original_data["username"]
    assert payload["email"] == original_data["email"]
    assert payload["full_name"] == original_data["full_name"]


def test_multiple_tokens_are_different():
    """Test that creating multiple tokens produces different results."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    
    token1 = create_access_token({"username": "user1"}, config)
    token2 = create_access_token({"username": "user2"}, config)
    
    assert token1 != token2


def test_same_data_produces_different_tokens():
    """Test that same data produces different tokens due to timestamp."""
    config = JWTConfig(jwt_secret_key="a" * 32)
    data = {"username": "testuser"}
    
    token1 = create_access_token(data, config)
    # Small delay to ensure different timestamp
    import time
    time.sleep(0.01)
    token2 = create_access_token(data, config)
    
    # Tokens should be different due to different exp timestamps
    assert token1 != token2
    
    # But both should verify successfully
    assert verify_token(token1, config) is not None
    assert verify_token(token2, config) is not None
