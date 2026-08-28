"""Secret provider abstraction and reference resolver.

This module provides:
- SecretProvider: Abstract base class for vault/secret manager integrations.
- SecretReference: Parsed representation of a vault:// URI.
- resolve_value(): Recursively resolves vault references in config dicts/lists.
- register_provider(): Registers a provider instance by name.
- parse_reference(): Parses a vault:// URI string.

Vault reference format:
    vault://<provider>/<path>#<key>

Examples:
    vault://hashicorp/database/postgres#password
    vault://hashicorp/opensearch/credentials#username
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from docpipe.exceptions.docpipe_exceptions import ConfigurationError
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

# Pattern: vault://provider/path/to/secret#key
_VAULT_REF_PATTERN = re.compile(r"^vault://([^/]+)/(.+?)(?:#(.+))?$")

# Global registry of providers
_providers: dict[str, "SecretProvider"] = {}


@dataclass(frozen=True)
class SecretReference:
    """Parsed vault reference URI.

    Attributes:
        provider: Name of the registered secret provider (e.g., "hashicorp").
        path: Path to the secret within the vault (e.g., "database/postgres").
        key: Optional key within a multi-value secret (e.g., "password").
    """

    provider: str
    path: str
    key: str | None = None


class SecretProvider(ABC):
    """Abstract base class for secret/vault providers.

    Implementations must handle:
    - Authentication (with automatic re-auth on token expiry)
    - Secret retrieval by path and optional key
    - Availability check
    """

    @abstractmethod
    def authenticate(self) -> None:
        """Authenticate with the vault backend.

        Raises:
            ConfigurationError: If credentials or configuration are invalid.
            ExternalServiceError: If the vault backend is unreachable or rejects the request.
        """

    @abstractmethod
    def get_secret(self, *, path: str, key: str | None = None) -> str:
        """Retrieve a secret value from the vault.

        Args:
            path: Path to the secret within the vault.
            key: Optional specific key within a multi-value secret.

        Returns:
            The secret value as a string.

        Raises:
            ExternalServiceError: If the key does not exist at the path or the secret cannot be retrieved.
            ConfigurationError: If no key is specified and the secret has multiple keys.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the vault provider is reachable and properly configured.

        Returns:
            True if the provider is available, False otherwise.
        """


def register_provider(*, name: str, provider: SecretProvider) -> None:
    """Register a secret provider instance by name.

    Args:
        name: Provider name used in vault:// URIs (e.g., "hashicorp").
        provider: An instance implementing SecretProvider.
    """
    _providers[name] = provider
    logger.info("Registered secret provider: %s", name)


def get_provider(*, name: str) -> SecretProvider | None:
    """Get a registered provider by name.

    Args:
        name: Provider name.

    Returns:
        The provider instance, or None if not registered.
    """
    return _providers.get(name)


def parse_reference(value: str) -> SecretReference | None:
    """Parse a vault:// reference string.

    Args:
        value: A string that may be a vault reference.

    Returns:
        SecretReference if the string matches vault:// format, None otherwise.
    """
    match = _VAULT_REF_PATTERN.match(value)
    if not match:
        return None
    return SecretReference(
        provider=match.group(1),
        path=match.group(2),
        key=match.group(3),
    )


def is_vault_reference(value: Any) -> bool:
    """Check if a value is a vault:// reference string.

    Args:
        value: Any value to check.

    Returns:
        True if the value is a string starting with 'vault://'.
    """
    return isinstance(value, str) and value.startswith("vault://")


def resolve_value(value: Any) -> Any:
    """Resolve vault references in a value, recursively.

    If the value is a vault:// reference string, fetches the secret from
    the registered provider. Works recursively on dicts and lists.
    Non-reference values are returned unchanged.

    Args:
        value: A string, dict, list, or any other value.

    Returns:
        The resolved value (secret fetched from vault, or original value).

    Raises:
        ConfigurationError: If the provider referenced in the URI is not registered, or the
            secret path has multiple keys and none is specified.
        ExternalServiceError: If the key does not exist at the vault path or the secret
            cannot be retrieved from the backend.
    """
    if isinstance(value, str):
        ref = parse_reference(value)
        if ref is None:
            return value

        provider = _providers.get(ref.provider)
        if provider is None:
            raise ConfigurationError(
                f"Secret provider '{ref.provider}' not registered. "
                "Vault initialization failed at startup — check logs for details. "
                "Common causes: VAULT_ROLE_ID/VAULT_SECRET_ID not set, "
                "or Vault unreachable at VAULT_ADDR. "
                "Enable debug logging with DS_LOG_LEVEL=DEBUG for full detail."
            )

        logger.debug("Resolving vault reference: provider=%s, path=%s, key=%s", ref.provider, ref.path, ref.key)
        return provider.get_secret(path=ref.path, key=ref.key)

    if isinstance(value, dict):
        return {k: resolve_value(v) for k, v in value.items()}

    if isinstance(value, list):
        return [resolve_value(item) for item in value]

    return value


def clear_providers() -> None:
    """Remove all registered providers. Primarily for testing."""
    _providers.clear()
