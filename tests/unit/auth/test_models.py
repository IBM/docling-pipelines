"""Unit tests for authentication models."""

import os

import pytest
from pydantic import ValidationError

from docpipe.api.auth.models import (
    LoginRequest,
    TokenResponse,
    User,
)


class TestLoginRequest:
    """Test LoginRequest model."""

    def test_login_request_valid(self):
        """Test creating valid login request."""
        pwd = os.environ.get("TEST_USER_PASSWORD", "test-model-pass")
        request = LoginRequest(username="testuser", password=pwd)

        assert request.username == "testuser"
        assert request.password == pwd

    def test_login_request_missing_username(self):
        """Test login request without username raises error."""
        with pytest.raises(ValidationError):
            LoginRequest(password=os.environ.get("TEST_USER_PASSWORD", "test-model-pass"))

    def test_login_request_missing_password(self):
        """Test login request without password raises error."""
        with pytest.raises(ValidationError):
            LoginRequest(username="testuser")

    def test_login_request_empty_values(self):
        """Test login request with empty values."""
        request = LoginRequest(username="", password="")

        assert request.username == ""
        assert request.password == ""


class TestTokenResponse:
    """Test TokenResponse model."""

    def test_token_response_valid(self):
        """Test creating valid token response."""
        response = TokenResponse(access_token="test-token")

        assert response.access_token == "test-token"
        assert response.token_type == "bearer"

    def test_token_response_custom_type(self):
        """Test token response with custom token type."""
        response = TokenResponse(access_token="test-token", token_type="custom")

        assert response.access_token == "test-token"
        assert response.token_type == "custom"

    def test_token_response_missing_token(self):
        """Test token response without access token raises error."""
        with pytest.raises(ValidationError):
            TokenResponse()

    def test_token_response_default_type(self):
        """Test token response has default type."""
        response = TokenResponse(access_token="test-token")

        assert response.token_type == "bearer"


class TestUser:
    """Test User model."""

    def test_user_valid(self):
        """Test creating valid user."""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
        )

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"

    def test_user_minimal(self):
        """Test creating user with only username."""
        user = User(username="testuser")

        assert user.username == "testuser"
        assert user.email == ""
        assert user.full_name == ""

    def test_user_missing_username(self):
        """Test user without username raises error."""
        with pytest.raises(ValidationError):
            User(email="test@example.com")

    def test_user_with_email_only(self):
        """Test user with username and email."""
        user = User(username="testuser", email="test@example.com")

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == ""

    def test_user_with_full_name_only(self):
        """Test user with username and full name."""
        user = User(username="testuser", full_name="Test User")

        assert user.username == "testuser"
        assert user.email == ""
        assert user.full_name == "Test User"

    def test_user_empty_optional_fields(self):
        """Test user with empty optional fields."""
        user = User(username="testuser", email="", full_name="")

        assert user.username == "testuser"
        assert user.email == ""
        assert user.full_name == ""

    def test_user_serialization(self):
        """Test user model serialization."""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
        )

        user_dict = user.model_dump()

        assert user_dict["username"] == "testuser"
        assert user_dict["email"] == "test@example.com"
        assert user_dict["full_name"] == "Test User"

    def test_user_from_dict(self):
        """Test creating user from dictionary."""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
        }

        user = User(**user_data)

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
