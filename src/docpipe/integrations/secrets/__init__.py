"""Secret provider integration for external vault/secret managers.

Supports resolving secret references in flow configurations using the
vault:// URI scheme. Credentials for vault connectivity are read from
environment variables (typically via .env file for local development).

Usage in flow.json:
    "password": ""  # pragma: allowlist secret

Supported providers:
    - hashicorp: HashiCorp Vault (AppRole authentication)

Adding new providers:
    1. Create a new module implementing SecretProvider
    2. Register it via register_provider()
"""

from docpipe.integrations.secrets.secret_provider import (
    SecretProvider,
    SecretReference,
    parse_reference,
    register_provider,
    resolve_value,
)

__all__ = [
    "SecretProvider",
    "SecretReference",
    "parse_reference",
    "register_provider",
    "resolve_value",
]
