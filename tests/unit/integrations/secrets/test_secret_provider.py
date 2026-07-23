"""Unit tests for SecretProvider base, reference parsing, and resolve_value."""

import pytest

from docpipe.exceptions.docpipe_exceptions import ConfigurationError, ExternalServiceError
from docpipe.integrations.secrets.secret_provider import (
    SecretProvider,
    SecretReference,
    clear_providers,
    is_vault_reference,
    parse_reference,
    register_provider,
    resolve_value,
)


class FakeProvider(SecretProvider):
    """Test implementation of SecretProvider."""

    def __init__(self, *, secrets: dict[str, dict[str, str]]) -> None:
        self._secrets = secrets

    def authenticate(self) -> None:
        pass

    def get_secret(self, *, path: str, key: str | None = None) -> str:
        data = self._secrets.get(path)
        if data is None:
            raise ExternalServiceError(f"Secret not found: {path}")
        if key:
            if key not in data:
                raise ExternalServiceError(f"Key '{key}' not found at path '{path}'")
            return data[key]
        if len(data) == 1:
            return next(iter(data.values()))
        raise ConfigurationError("Multiple keys, specify one")

    def is_available(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _cleanup_providers():
    """Ensure providers are cleared between tests."""
    clear_providers()
    yield
    clear_providers()


class TestParseReference:
    """Tests for parse_reference()."""

    def test_valid_reference_with_key(self):
        ref = parse_reference("vault://hashicorp/database/postgres#password")
        assert ref == SecretReference(provider="hashicorp", path="database/postgres", key="password")

    def test_valid_reference_without_key(self):
        ref = parse_reference("vault://hashicorp/api/token")
        assert ref == SecretReference(provider="hashicorp", path="api/token", key=None)

    def test_valid_reference_deep_path(self):
        ref = parse_reference("vault://hashicorp/a/b/c/d#mykey")
        assert ref == SecretReference(provider="hashicorp", path="a/b/c/d", key="mykey")

    def test_non_vault_reference_returns_none(self):
        assert parse_reference("just-a-string") is None
        assert parse_reference("") is None
        assert parse_reference("http://example.com") is None

    def test_different_provider(self):
        ref = parse_reference("vault://cyberark/safe/object#Content")
        assert ref == SecretReference(provider="cyberark", path="safe/object", key="Content")


class TestIsVaultReference:
    """Tests for is_vault_reference()."""

    def test_vault_reference(self):
        assert is_vault_reference("vault://hashicorp/path#key") is True

    def test_not_vault_reference(self):
        assert is_vault_reference("plain-value") is False
        assert is_vault_reference(123) is False
        assert is_vault_reference(None) is False
        assert is_vault_reference({"key": "value"}) is False


class TestRegisterProvider:
    """Tests for register_provider()."""

    def test_register_and_use(self):
        provider = FakeProvider(secrets={"test/path": {"key": "secret_value"}})
        register_provider(name="fake", provider=provider)

        result = resolve_value("vault://fake/test/path#key")
        assert result == "secret_value"


class TestResolveValue:
    """Tests for resolve_value()."""

    def test_non_vault_string_unchanged(self):
        assert resolve_value("hello") == "hello"
        assert resolve_value("") == ""

    def test_non_string_types_unchanged(self):
        assert resolve_value(42) == 42
        assert resolve_value(3.14) == 3.14
        assert resolve_value(True) is True
        assert resolve_value(None) is None

    def test_vault_reference_resolved(self):
        provider = FakeProvider(secrets={"db/creds": {"user": "admin", "pass": "s3cret"}})
        register_provider(name="hashicorp", provider=provider)

        assert resolve_value("vault://hashicorp/db/creds#user") == "admin"
        assert resolve_value("vault://hashicorp/db/creds#pass") == "s3cret"

    def test_dict_with_mixed_values(self):
        provider = FakeProvider(secrets={"db/creds": {"password": "vault_pass"}})
        register_provider(name="hashicorp", provider=provider)

        config = {
            "host": "localhost",
            "port": 5432,
            "password": "vault://hashicorp/db/creds#password",  # pragma: allowlist secret
            "ssl": True,
        }

        resolved = resolve_value(config)
        assert resolved == {
            "host": "localhost",
            "port": 5432,
            "password": "vault_pass",  # pragma: allowlist secret
            "ssl": True,
        }

    def test_list_with_vault_references(self):
        provider = FakeProvider(
            secrets={
                "keys/api1": {"value": "key1"},
                "keys/api2": {"value": "key2"},
            }
        )
        register_provider(name="hashicorp", provider=provider)

        values = [
            "vault://hashicorp/keys/api1#value",
            "plain_value",
            "vault://hashicorp/keys/api2#value",
        ]

        resolved = resolve_value(values)
        assert resolved == ["key1", "plain_value", "key2"]

    def test_nested_dict_resolution(self):
        provider = FakeProvider(secrets={"opensearch/auth": {"password": "os_pass"}})
        register_provider(name="hashicorp", provider=provider)

        config = {
            "provider_config": {
                "host": "localhost",
                "password": "vault://hashicorp/opensearch/auth#password",  # pragma: allowlist secret
            }
        }

        resolved = resolve_value(config)
        assert resolved["provider_config"]["password"] == "os_pass"  # pragma: allowlist secret
        assert resolved["provider_config"]["host"] == "localhost"

    def test_unregistered_provider_raises_configuration_error(self):
        with pytest.raises(ConfigurationError, match="not registered"):
            resolve_value("vault://unknown/path#key")

    def test_missing_key_raises_external_service_error(self):
        provider = FakeProvider(secrets={"db/creds": {"user": "admin"}})
        register_provider(name="hashicorp", provider=provider)

        with pytest.raises(ExternalServiceError):
            resolve_value("vault://hashicorp/db/creds#nonexistent")

    def test_missing_path_raises_external_service_error(self):
        provider = FakeProvider(secrets={})
        register_provider(name="hashicorp", provider=provider)

        with pytest.raises(ExternalServiceError):
            resolve_value("vault://hashicorp/no/such/path#key")
