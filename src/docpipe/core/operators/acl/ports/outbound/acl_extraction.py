"""Port interface for ACL extraction.

This module defines the abstract port interface for ACL extraction following
hexagonal architecture principles. Adapters must implement this interface to
provide ACL extraction capabilities for different providers (SharePoint, S3, etc.).
"""

import logging
from abc import ABC, abstractmethod
from typing import TypeVar

from docpipe.core.operators.acl.domain.models import ACLRequest, ACLResponse

logger = logging.getLogger(__name__)

# Generic type for adapter-specific configuration
ACLConfig = TypeVar("ACLConfig")


class ACLExtractionPort[ACLConfig](ABC):
    """Abstract port interface for ACL extraction.

    This interface defines the contract that all ACL extraction adapters must
    implement. It provides methods for extracting ACLs, resolving inheritance,
    expanding groups, and normalizing identities.

    Adapters should implement this interface to provide ACL extraction for
    specific providers (SharePoint, S3, Google Drive, etc.).

    Note: ACLs are always fetched fresh on each flow run. No caching is performed
    to ensure the latest permissions are always retrieved.

    Type Parameters:
        ACLConfig: Provider-specific configuration type
    """

    @abstractmethod
    async def extract_acl(self, *, request: ACLRequest) -> ACLResponse:
        """Extract effective ACL for a single resource.

        This method extracts the effective allowed/denied users for a resource
        by performing the following steps:
        1. Fetch raw permissions from the provider
        2. Resolve inheritance recursively if requested
        3. Expand groups transitively if requested
        4. Normalize identities if requested
        5. Return effective allowed/denied users

        Note: Always fetches fresh data from the provider, no caching.

        Args:
            request: ACL extraction request with resource details and options

        Returns:
            ACLResponse containing effective allowed users and metadata

        Raises:
            Exception: If extraction fails (should be caught and returned in response)
        """
        ...

    @abstractmethod
    async def extract_acls_batch(self, *, requests: list[ACLRequest]) -> list[ACLResponse]:
        """Extract ACLs for multiple resources in batch.

        This method processes multiple ACL extraction requests, fetching fresh
        ACL data for each resource from the provider.

        Args:
            requests: List of ACL extraction requests

        Returns:
            List of ACL responses in the same order as requests

        Raises:
            Exception: If batch extraction fails
        """
        ...

    @abstractmethod
    async def resolve_inheritance(self, *, resource_id: str, resource_type: str, config: ACLConfig) -> list[str]:
        """Recursively resolve inheritance chain for a resource.

        This method traverses the inheritance hierarchy from the resource up to
        the root, returning the chain of resource IDs. The chain is ordered from
        the resource itself to the root.

        For example, for a SharePoint file:
        [file_id, folder_id, library_id, site_id, parent_site_id, root_site_id]

        Args:
            resource_id: Unique identifier for the resource
            resource_type: Type of resource (e.g., "file", "folder", "site")
            config: Provider-specific configuration

        Returns:
            List of resource IDs from item to root

        Raises:
            Exception: If inheritance resolution fails
        """
        ...

    @abstractmethod
    async def expand_group(self, *, group_id: str, config: ACLConfig) -> set[str]:
        """Expand group to transitive members.

        This method expands a group to its transitive members (including nested
        groups) and returns the set of normalized user identities.

        Args:
            group_id: Unique identifier for the group
            config: Provider-specific configuration

        Returns:
            Set of normalized user identities (emails/UPNs)

        Raises:
            Exception: If group expansion fails
        """
        ...

    @abstractmethod
    def normalize_identity(self, *, principal_id: str, principal_type: str, config: ACLConfig) -> str:
        """Normalize identity to canonical form (email/UPN).

        This method converts provider-specific identity formats to a canonical
        form (typically lowercase email or UPN). It handles various formats:

        - user@domain.com -> user@domain.com
        - i:0#.f|membership|user@domain.com -> user@domain.com (SharePoint)
        - GUIDs -> lookup email (if supported)
        - AAD object IDs -> lookup email (if supported)

        Args:
            principal_id: Provider-specific principal identifier
            principal_type: Type of principal ("user", "group", etc.)
            config: Provider-specific configuration

        Returns:
            Normalized identity string (lowercase email/UPN)

        Raises:
            Exception: If normalization fails
        """
        ...

    @abstractmethod
    async def test_connection(self, *, config: ACLConfig) -> bool:
        """Test connection to the provider.

        This method verifies that the adapter can successfully connect to the
        provider using the provided configuration and credentials.

        Args:
            config: Provider-specific configuration

        Returns:
            True if connection is successful, False otherwise
        """
        ...

    @abstractmethod
    def build_config_from_operator_params(
        self, *, connection_params: dict, credentials: dict, provider_metadata: dict
    ) -> ACLConfig:
        """Build provider-specific configuration from operator parameters.

        This method constructs the adapter's configuration object from the
        generic parameters provided by the operator. It validates and transforms
        the parameters into the format expected by the adapter.

        Args:
            connection_params: Connection parameters from operator
            credentials: Authentication credentials from operator
            provider_metadata: Provider-specific metadata from operator

        Returns:
            Provider-specific configuration object

        Raises:
            ValueError: If parameters are invalid or missing
        """
        ...
