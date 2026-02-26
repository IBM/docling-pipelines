#!/usr/bin/env python3
"""
Simple script to test OpenSearch connectivity
Requires .env file with connection details
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, 'src')

# Check if .env file exists
env_file = Path('.env')
if not env_file.exists():
    print("❌ .env file not found!")
    print("   This test requires OpenSearch connection details in .env file")
    print("   Copy .env.example to .env and update with your connection details")
    sys.exit(0)

from opensearchpy import OpenSearch
from common.util.env_config import get_env_var, get_env_bool, get_env_int

# Load connection details from environment
host = get_env_var('OPENSEARCH_HOST')
port = get_env_int('OPENSEARCH_PORT', 9200)
username = get_env_var('OPENSEARCH_USERNAME')
password = get_env_var('OPENSEARCH_PASSWORD')
use_ssl = get_env_bool('OPENSEARCH_USE_SSL', False)
verify_certs = get_env_bool('OPENSEARCH_VERIFY_CERTS', False)

if not host or not username or not password:
    print("❌ Missing required environment variables!")
    print("   Required: OPENSEARCH_HOST, OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD")
    sys.exit(1)

# Test different connection configurations
configs = [
    {
        "name": "HTTP without SSL",
        "hosts": [{'host': host, 'port': port}],
        "http_auth": (username, password),
        "use_ssl": False,
        "verify_certs": False,
        "ssl_show_warn": False
    },
    {
        "name": "HTTPS with SSL (from env)",
        "hosts": [{'host': host, 'port': port}],
        "http_auth": (username, password),
        "use_ssl": use_ssl,
        "verify_certs": verify_certs,
        "ssl_show_warn": False
    }
]

print(f"Testing connection to: {host}:{port}")
print(f"Using SSL: {use_ssl}")

for config in configs:
    print(f"\n{'='*60}")
    print(f"Testing: {config['name']}")
    print(f"{'='*60}")
    
    try:
        name = config.pop('name')
        client = OpenSearch(**config)
        
        # Try to get cluster info
        info = client.info()
        print(f"✅ SUCCESS!")
        print(f"   Cluster: {info.get('cluster_name', 'N/A')}")
        print(f"   Version: {info.get('version', {}).get('number', 'N/A')}")
        print(f"   Distribution: {info.get('version', {}).get('distribution', 'N/A')}")
        
        # Try to list indices
        indices = client.cat.indices(format='json')
        print(f"   Indices: {len(indices)} found")
        
        break  # Stop on first success
        
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {str(e)[:100]}")

print(f"\n{'='*60}")

# Made with Bob
