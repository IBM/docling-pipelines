#!/usr/bin/env python3
"""
Simple script to test OpenSearch connectivity
Requires .env file with connection details
"""

import sys
from pathlib import Path

import pytest
from opensearchpy import OpenSearch

from docpipe.utils.infrastructure.config import get_env_bool, get_env_int, get_env_var

# Check if .env file exists
env_file = Path(".env")
if not env_file.exists():
    pytest.skip(
        ".env file not found. This test requires OpenSearch connection details. "
        "Copy .env.example to .env and update with your connection details.",
        allow_module_level=True,
    )

# Load connection details from environment
host = get_env_var("OPENSEARCH_HOST")
port = get_env_int("OPENSEARCH_PORT", 9200)
username = get_env_var("OPENSEARCH_USERNAME")
password = get_env_var("OPENSEARCH_PASSWORD")
use_ssl = get_env_bool("OPENSEARCH_USE_SSL", False)
verify_certs = get_env_bool("OPENSEARCH_VERIFY_CERTS", False)

if not host or not username or not password:
    print("❌ Missing required environment variables!")
    print("   Required: OPENSEARCH_HOST, OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD")
    sys.exit(1)

# Test different connection configurations
configs = [
    {
        "name": "HTTP without SSL",
        "hosts": [{"host": host, "port": port}],
        "http_auth": (username, password),
        "use_ssl": False,
        "verify_certs": False,
        "ssl_show_warn": False,
    },
    {
        "name": "HTTPS with SSL (from env)",
        "hosts": [{"host": host, "port": port}],
        "http_auth": (username, password),
        "use_ssl": use_ssl,
        "verify_certs": verify_certs,
        "ssl_show_warn": False,
    },
]

print(f"Testing connection to: {host}:{port}")
print(f"Using SSL: {use_ssl}")

for config in configs:
    print(f"\n{'=' * 60}")
    print(f"Testing: {config['name']}")
    print(f"{'=' * 60}")

    try:
        name = config.pop("name")
        client = OpenSearch(**config)

        # Try to get cluster info
        info = client.info()
        print("✅ SUCCESS!")
        print(f"   Cluster: {info.get('cluster_name', 'N/A')}")
        print(f"   Version: {info.get('version', {}).get('number', 'N/A')}")
        print(f"   Distribution: {info.get('version', {}).get('distribution', 'N/A')}")

        # Try to list indices
        indices = client.cat.indices(format="json")
        print(f"   Indices: {len(indices)} found")

        break  # Stop on first success

    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {str(e)[:100]}")

print(f"\n{'=' * 60}")


# JWT Authentication Tests
def test_jwt_token_from_environment():
    """Test loading JWT token from environment variable."""
    import os

    # pragma: allowlist secret
    test_token = "test-jwt-token-for-testing-only"  # pragma: allowlist secret
    os.environ["OPENSEARCH_JWT_TOKEN"] = test_token

    from docpipe.utils.infrastructure.config import get_opensearch_config

    config = get_opensearch_config()

    # JWT token should be in provider_config
    assert "provider_config" in config
    assert "jwt_token" in config["provider_config"]
    assert config["provider_config"]["jwt_token"] == test_token

    # Clean up
    del os.environ["OPENSEARCH_JWT_TOKEN"]


print("\nJWT Authentication support added!")
print("Set OPENSEARCH_JWT_TOKEN environment variable to use JWT authentication")
