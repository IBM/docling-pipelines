#!/usr/bin/env python3
"""
OpenSearch Client
Handles connection setup, authentication, and lifecycle management for OpenSearch.
"""

from typing import Any

import boto3
from botocore.credentials import Credentials
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

from common.util.infrastructure.logging import get_logger

logger = get_logger()


class OpenSearchClient:
    """
    Manages OpenSearch client connection and authentication.
    
    Responsibilities:
    - Connection setup with various authentication methods
    - Client lifecycle management
    - Version detection
    - Connection validation
    """

    def __init__(
        self,
        host: str,
        port: int = 9200,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool = True,
        verify_certs: bool = True,
        aws_auth: bool = False,
        aws_region: str | None = None,
        timeout: int = 60,
    ) -> None:
        """
        Initialize OpenSearch client with connection parameters.

        Args:
            host: OpenSearch server host
            port: OpenSearch server port
            username: Username for basic authentication
            password: Password for basic authentication
            use_ssl: Use SSL connection
            verify_certs: Verify SSL certificates
            aws_auth: Use AWS IAM authentication
            aws_region: AWS region for authentication
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.verify_certs = verify_certs
        self.aws_auth = aws_auth
        self.aws_region = aws_region
        self.timeout = timeout
        
        self._client: OpenSearch | None = None
        self._version: tuple[int, int, int] | None = None

    def _validate_parameters(self) -> None:
        """Validate connection parameters."""
        if not self.host:
            raise ValueError("opensearch_host is required")
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("opensearch_host must be a non-empty string")
        
        if not isinstance(self.port, int):
            raise ValueError("opensearch_port must be an integer")
        if self.port < 1 or self.port > 65535:
            raise ValueError("opensearch_port must be between 1 and 65535")
        
        if self.aws_auth and not self.aws_region:
            raise ValueError("aws_region is required when aws_auth is enabled")

    def connect(self) -> OpenSearch:
        """
        Create and return an OpenSearch client with appropriate authentication.
        
        Returns:
            Configured OpenSearch client
            
        Raises:
            ValueError: If connection parameters are invalid
        """
        self._validate_parameters()
        
        connection_params: dict[str, Any] = {
            "hosts": [{"host": self.host, "port": self.port}],
            "use_ssl": self.use_ssl,
            "verify_certs": self.verify_certs,
            "connection_class": RequestsHttpConnection,
            "timeout": self.timeout,
        }

        # Add authentication
        if self.aws_auth:
            credentials: Credentials | None = boto3.Session().get_credentials()
            auth: AWSV4SignerAuth = AWSV4SignerAuth(credentials, self.aws_region or "us-east-1")
            connection_params["http_auth"] = auth
        elif self.username and self.password:
            connection_params["http_auth"] = (self.username, self.password)

        self._client = OpenSearch(**connection_params)
        logger.info(f"Connected to OpenSearch at {self.host}:{self.port}")
        
        return self._client

    def get_client(self) -> OpenSearch:
        """
        Get the OpenSearch client, creating it if necessary.
        
        Returns:
            OpenSearch client instance
        """
        if self._client is None:
            self._client = self.connect()
        return self._client

    def get_version(self) -> tuple[int, int, int]:
        """
        Get OpenSearch server version.
        
        Returns:
            Version tuple (major, minor, patch)
        """
        if self._version is not None:
            return self._version
            
        try:
            client = self.get_client()
            info: dict[str, Any] = client.info()
            version_string: str = info.get("version", {}).get("number", "0.0.0")
            parts: list[str] = version_string.split(".")
            version_tuple: tuple[int, int, int] = tuple(int(p) for p in parts[:3])  # type: ignore
            self._version = version_tuple
            logger.info(f"OpenSearch version: {'.'.join(map(str, version_tuple))}")
            return version_tuple
        except Exception as e:
            logger.warning(f"Could not retrieve OpenSearch version: {e}")
            self._version = (0, 0, 0)
            return (0, 0, 0)

    def test_connection(self) -> bool:
        """
        Test the connection to OpenSearch.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            client = self.get_client()
            client.info()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def close(self) -> None:
        """Close the OpenSearch client connection."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("OpenSearch client connection closed")
            except Exception as e:
                logger.warning(f"Error closing OpenSearch client: {e}")
            finally:
                self._client = None
                self._version = None
