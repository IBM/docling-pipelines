"""Unit tests for LDAP authentication module."""

from unittest.mock import MagicMock, patch

import ldap
import pytest

from docpipe.api.auth.ldap_auth import LDAPAuthenticator, LDAPConfig
from docpipe.api.auth.models import User
from docpipe.exceptions.docpipe_exceptions import ConfigurationError, ExternalServiceError


# ---------------------------------------------------------------------------
# LDAPConfig tests
# ---------------------------------------------------------------------------


def test_ldap_config_default_values():
    """Test that LDAPConfig has expected default values."""
    config = LDAPConfig()
    assert config.ldap_server == ""
    assert config.ldap_base_dn == ""
    assert config.ldap_user_dn == ""
    assert config.ldap_bind_dn == ""
    assert config.ldap_bind_password == ""
    assert config.ldap_use_ssl is False
    assert config.ldap_use_active_directory is False
    assert config.ldap_ad_domain == ""


def test_ldap_config_custom_values():
    """Test that LDAPConfig accepts custom values."""
    config = LDAPConfig(
        ldap_server="ldap://localhost:389",
        ldap_base_dn="dc=example,dc=com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="secret",  # pragma: allowlist secret
        ldap_use_ssl=True,
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    assert config.ldap_server == "ldap://localhost:389"
    assert config.ldap_base_dn == "dc=example,dc=com"
    assert config.ldap_user_dn == "ou=users,dc=example,dc=com"
    assert config.ldap_bind_dn == "cn=admin,dc=example,dc=com"
    assert config.ldap_bind_password == "secret"  # pragma: allowlist secret
    assert config.ldap_use_ssl is True
    assert config.ldap_use_active_directory is True
    assert config.ldap_ad_domain == "example.com"


# ---------------------------------------------------------------------------
# LDAPAuthenticator initialization tests
# ---------------------------------------------------------------------------


def test_ldap_authenticator_initialization():
    """Test that LDAPAuthenticator initializes with config."""
    config = LDAPConfig(ldap_server="ldap://localhost:389")
    authenticator = LDAPAuthenticator(config)
    assert authenticator.config == config


# ---------------------------------------------------------------------------
# Active Directory authentication tests
# ---------------------------------------------------------------------------


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_ad_authenticate_success(mock_initialize):
    """Test successful Active Directory authentication."""
    config = LDAPConfig(
        ldap_server="ldap://ad.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.search_s.return_value = [
        (
            "CN=Test User,OU=Users,DC=example,DC=com",
            {
                "cn": [b"Test User"],
                "mail": [b"testuser@example.com"],
                "sAMAccountName": [b"testuser"],
            },
        )
    ]

    user = authenticator.authenticate("testuser", "password123")

    assert user is not None
    assert user.username == "testuser"
    assert user.email == "testuser@example.com"
    assert user.full_name == "Test User"
    mock_client.simple_bind_s.assert_called_once_with("testuser@example.com", "password123")


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_ad_authenticate_invalid_credentials(mock_initialize):
    """Test Active Directory authentication with invalid credentials."""
    config = LDAPConfig(
        ldap_server="ldap://ad.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.simple_bind_s.side_effect = ldap.INVALID_CREDENTIALS

    user = authenticator.authenticate("testuser", "wrongpassword")

    assert user is None


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_ad_authenticate_missing_domain_raises_error(mock_initialize):
    """Test Active Directory authentication without domain raises ConfigurationError."""
    config = LDAPConfig(
        ldap_server="ldap://ad.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_use_active_directory=True,
        ldap_ad_domain="",  # Missing domain
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client

    with pytest.raises(ConfigurationError, match="ldap_ad_domain must be configured"):
        authenticator.authenticate("testuser", "password123")


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_ad_authenticate_with_ssl(mock_initialize):
    """Test Active Directory authentication with SSL enabled."""
    config = LDAPConfig(
        ldap_server="ldaps://ad.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
        ldap_use_ssl=True,
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.search_s.return_value = [
        (
            "CN=Test User,OU=Users,DC=example,DC=com",
            {"cn": [b"Test User"], "mail": [b"test@example.com"]},
        )
    ]

    user = authenticator.authenticate("testuser", "password123")

    assert user is not None
    mock_client.start_tls_s.assert_called_once()


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_ad_authenticate_missing_email(mock_initialize):
    """Test Active Directory authentication with missing email attribute."""
    config = LDAPConfig(
        ldap_server="ldap://ad.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.search_s.return_value = [
        ("CN=Test User,OU=Users,DC=example,DC=com", {"cn": [b"Test User"]})
    ]

    user = authenticator.authenticate("testuser", "password123")

    assert user is not None
    assert user.email == ""
    assert user.full_name == "Test User"


# ---------------------------------------------------------------------------
# Standard LDAP authentication tests
# ---------------------------------------------------------------------------


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_standard_ldap_authenticate_success(mock_initialize):
    """Test successful standard LDAP authentication."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
        ldap_use_active_directory=False,
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.search_s.return_value = [
        (
            "uid=testuser,ou=users,dc=example,dc=com",
            {"cn": [b"Test User"], "mail": [b"test@example.com"], "uid": [b"testuser"]},
        )
    ]

    user = authenticator.authenticate("testuser", "password123")

    assert user is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.full_name == "Test User"


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_standard_ldap_authenticate_user_not_found(mock_initialize):
    """Test standard LDAP authentication when user is not found."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
        ldap_use_active_directory=False,
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.search_s.return_value = []  # User not found

    user = authenticator.authenticate("nonexistent", "password123")

    assert user is None


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_standard_ldap_authenticate_invalid_credentials(mock_initialize):
    """Test standard LDAP authentication with invalid credentials."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
        ldap_use_active_directory=False,
    )
    authenticator = LDAPAuthenticator(config)

    # First call for admin bind succeeds, second call for user bind fails
    mock_client_admin = MagicMock()
    mock_client_user = MagicMock()
    mock_initialize.side_effect = [mock_client_admin, mock_client_user]

    mock_client_admin.search_s.return_value = [
        ("uid=testuser,ou=users,dc=example,dc=com", {"cn": [b"Test User"]})
    ]
    mock_client_user.simple_bind_s.side_effect = ldap.INVALID_CREDENTIALS

    user = authenticator.authenticate("testuser", "wrongpassword")

    assert user is None


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_standard_ldap_authenticate_with_ssl(mock_initialize):
    """Test standard LDAP authentication with SSL enabled."""
    config = LDAPConfig(
        ldap_server="ldaps://ldap.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
        ldap_use_ssl=True,
        ldap_use_active_directory=False,
    )
    authenticator = LDAPAuthenticator(config)

    mock_client_admin = MagicMock()
    mock_client_user = MagicMock()
    mock_initialize.side_effect = [mock_client_admin, mock_client_user]

    mock_client_admin.search_s.return_value = [
        ("uid=testuser,ou=users,dc=example,dc=com", {"cn": [b"Test User"]})
    ]

    user = authenticator.authenticate("testuser", "password123")

    assert user is not None
    # SSL should be started on both connections
    assert mock_client_admin.start_tls_s.call_count == 1
    assert mock_client_user.start_tls_s.call_count == 1


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_standard_ldap_authenticate_missing_attributes(mock_initialize):
    """Test standard LDAP authentication with missing email and name attributes."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
        ldap_use_active_directory=False,
    )
    authenticator = LDAPAuthenticator(config)

    mock_client_admin = MagicMock()
    mock_client_user = MagicMock()
    mock_initialize.side_effect = [mock_client_admin, mock_client_user]

    mock_client_admin.search_s.return_value = [
        ("uid=testuser,ou=users,dc=example,dc=com", {"uid": [b"testuser"]})
    ]

    user = authenticator.authenticate("testuser", "password123")

    assert user is not None
    assert user.username == "testuser"
    assert user.email == ""
    assert user.full_name == ""


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_authenticate_server_down_raises_external_service_error(mock_initialize):
    """Test that SERVER_DOWN exception raises ExternalServiceError."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.simple_bind_s.side_effect = ldap.SERVER_DOWN

    with pytest.raises(ExternalServiceError, match="LDAP server is unavailable"):
        authenticator.authenticate("testuser", "password123")


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_authenticate_invalid_dn_syntax_raises_configuration_error(mock_initialize):
    """Test that INVALID_DN_SYNTAX exception raises ConfigurationError."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.simple_bind_s.side_effect = ldap.INVALID_DN_SYNTAX("Invalid DN")

    with pytest.raises(ConfigurationError, match="invalid bind DN format"):
        authenticator.authenticate("testuser", "password123")


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_authenticate_unexpected_exception_raises_external_service_error(mock_initialize):
    """Test that unexpected exceptions raise ExternalServiceError."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.simple_bind_s.side_effect = Exception("Unexpected error")

    with pytest.raises(ExternalServiceError, match="LDAP authentication error"):
        authenticator.authenticate("testuser", "password123")


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_authenticate_unbind_error_is_logged(mock_initialize, caplog):
    """Test that unbind errors are logged but don't prevent authentication."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.search_s.return_value = [
        ("CN=Test User,OU=Users,DC=example,DC=com", {"cn": [b"Test User"]})
    ]
    mock_client.unbind_s.side_effect = Exception("Unbind failed")

    with caplog.at_level("ERROR"):
        user = authenticator.authenticate("testuser", "password123")

    assert user is not None
    assert "Failed to unbind LDAP connection" in caplog.text


# ---------------------------------------------------------------------------
# verify_connection tests
# ---------------------------------------------------------------------------


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_verify_connection_success(mock_initialize):
    """Test successful LDAP connection verification."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client

    result = authenticator.verify_connection()

    assert result is True
    mock_client.simple_bind_s.assert_called_once_with(
        "cn=admin,dc=example,dc=com", "adminpass"  # pragma: allowlist secret
    )


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_verify_connection_failure(mock_initialize):
    """Test LDAP connection verification failure."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.simple_bind_s.side_effect = Exception("Connection failed")

    result = authenticator.verify_connection()

    assert result is False


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_verify_connection_with_ssl(mock_initialize):
    """Test LDAP connection verification with SSL enabled."""
    config = LDAPConfig(
        ldap_server="ldaps://ldap.example.com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
        ldap_use_ssl=True,
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client

    result = authenticator.verify_connection()

    assert result is True
    mock_client.start_tls_s.assert_called_once()


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_verify_connection_unbind_error_is_logged(mock_initialize, caplog):
    """Test that unbind errors during verification are logged."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.unbind_s.side_effect = Exception("Unbind failed")

    with caplog.at_level("ERROR"):
        result = authenticator.verify_connection()

    assert result is True
    assert "Error unbinding LDAP connection" in caplog.text


# ---------------------------------------------------------------------------
# Logging tests
# ---------------------------------------------------------------------------


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_authenticate_logs_success(mock_initialize, caplog):
    """Test that successful authentication is logged."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.search_s.return_value = [
        ("CN=Test User,OU=Users,DC=example,DC=com", {"cn": [b"Test User"]})
    ]

    with caplog.at_level("INFO"):
        authenticator.authenticate("testuser", "password123")

    assert "Successfully authenticated user: testuser" in caplog.text


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_authenticate_logs_invalid_credentials(mock_initialize, caplog):
    """Test that invalid credentials are logged."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_use_active_directory=True,
        ldap_ad_domain="example.com",
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.simple_bind_s.side_effect = ldap.INVALID_CREDENTIALS

    with caplog.at_level("WARNING"):
        authenticator.authenticate("testuser", "wrongpassword")

    assert "Invalid credentials for user: testuser" in caplog.text


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_authenticate_logs_user_not_found(mock_initialize, caplog):
    """Test that user not found is logged."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_user_dn="ou=users,dc=example,dc=com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
        ldap_use_active_directory=False,
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.search_s.return_value = []

    with caplog.at_level("WARNING"):
        authenticator.authenticate("nonexistent", "password123")

    assert "User not found in LDAP: nonexistent" in caplog.text


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_verify_connection_logs_success(mock_initialize, caplog):
    """Test that successful connection verification is logged."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client

    with caplog.at_level("INFO"):
        authenticator.verify_connection()

    assert "LDAP connection verified successfully" in caplog.text


@patch("docpipe.api.auth.ldap_auth.ldap.initialize")
def test_verify_connection_logs_failure(mock_initialize, caplog):
    """Test that connection verification failure is logged."""
    config = LDAPConfig(
        ldap_server="ldap://ldap.example.com",
        ldap_bind_dn="cn=admin,dc=example,dc=com",
        ldap_bind_password="adminpass",  # pragma: allowlist secret
    )
    authenticator = LDAPAuthenticator(config)

    mock_client = MagicMock()
    mock_initialize.return_value = mock_client
    mock_client.simple_bind_s.side_effect = Exception("Connection failed")

    with caplog.at_level("ERROR"):
        authenticator.verify_connection()

    assert "LDAP connection verification failed" in caplog.text
