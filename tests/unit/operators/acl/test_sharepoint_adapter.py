"""Unit tests for SharePoint ACL Adapter."""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.operators.acl.adapters.outbound.sharepoint_adapter import (
    SharePointACLAdapter,
    SharePointACLConfig,
)
from docpipe.core.operators.acl.domain.models import ACLResponse, RawPermission
from docpipe.exceptions.docpipe_exceptions import (
    ConfigurationError,
    ExternalServiceError,
)


class TestSharePointACLAdapterInitialization:
    """Test SharePoint adapter initialization."""

    def test_init_creates_empty_caches(self):
        """Test adapter initialization creates empty caches."""
        adapter = SharePointACLAdapter()

        assert hasattr(adapter, "_token_cache")
        assert hasattr(adapter, "_group_cache")
        assert hasattr(adapter, "_identity_cache")
        assert isinstance(adapter._token_cache, dict)
        assert isinstance(adapter._group_cache, dict)
        assert isinstance(adapter._identity_cache, dict)

    def test_adapter_metadata(self):
        """Test adapter has correct metadata."""
        adapter = SharePointACLAdapter()

        assert adapter.ADAPTER_NAME == "sharepoint"
        assert "SharePoint" in adapter.ADAPTER_DISPLAY_NAME
        assert "ACL" in adapter.ADAPTER_DISPLAY_NAME


class TestSharePointACLConfig:
    """Test SharePoint configuration model."""

    def test_config_with_required_fields(self, sharepoint_config_dict):
        """Test config creation with required fields."""
        config = SharePointACLConfig(**sharepoint_config_dict)

        assert config.client_id == "test-client-id"
        assert config.client_secret == "test-client-secret"  # pragma: allowlist secret
        assert config.tenant_id == "test-tenant-id"
        assert config.drive_id == "test-drive-id"

    def test_config_with_default_values(self):
        """Test config uses default values for optional fields."""
        config = SharePointACLConfig(
            client_id="test-client-id",
            client_secret="test-client-secret",  # pragma: allowlist secret
            tenant_id="test-tenant-id",
            drive_id="test-drive-id",
        )

        assert config.resolve_inheritance is True
        assert config.expand_groups is True
        assert config.normalize_identities is True
        assert config.max_concurrent_requests == 5
        assert config.request_timeout == 60

    def test_config_with_custom_values(self):
        """Test config with custom values."""
        config = SharePointACLConfig(
            client_id="test-client-id",
            client_secret="test-client-secret",  # pragma: allowlist secret
            tenant_id="test-tenant-id",
            drive_id="test-drive-id",
            resolve_inheritance=False,
            expand_groups=False,
            normalize_identities=False,
            max_concurrent_requests=10,
            request_timeout=120,
        )

        assert config.resolve_inheritance is False
        assert config.expand_groups is False
        assert config.normalize_identities is False
        assert config.max_concurrent_requests == 10
        assert config.request_timeout == 120


class TestBuildConfigFromOperatorParams:
    """Test building SharePoint config from operator parameters."""

    def test_build_config_success(self):
        """Test successful config building."""
        adapter = SharePointACLAdapter()

        connection_params = {
            "drive_id": "test-drive-id",
            "timeout": 30,
            "resolve_inheritance": True,
            "expand_groups": True,
            "normalize_identities": True,
        }
        credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # pragma: allowlist secret
            "tenant_id": "test-tenant-id",
        }
        provider_metadata: dict[str, str] = {}

        config = adapter.build_config_from_operator_params(
            connection_params=connection_params, credentials=credentials, provider_metadata=provider_metadata
        )

        assert isinstance(config, SharePointACLConfig)
        assert config.client_id == "test-client-id"
        assert config.drive_id == "test-drive-id"

    def test_build_config_drive_id_from_provider_metadata(self):
        """Test drive_id can come from provider_metadata."""
        adapter = SharePointACLAdapter()

        connection_params: dict[str, str] = {}
        credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # pragma: allowlist secret
            "tenant_id": "test-tenant-id",
        }
        provider_metadata = {"drive_id": "test-drive-id-from-metadata"}

        config = adapter.build_config_from_operator_params(
            connection_params=connection_params, credentials=credentials, provider_metadata=provider_metadata
        )

        assert config.drive_id == "test-drive-id-from-metadata"

    def test_build_config_missing_client_id(self):
        """Test config building fails with missing client_id."""
        adapter = SharePointACLAdapter()

        connection_params = {"drive_id": "test-drive-id"}
        credentials = {"client_secret": "test-client-secret", "tenant_id": "test-tenant-id"}  # pragma: allowlist secret
        provider_metadata: dict[str, str] = {}

        with pytest.raises(ConfigurationError) as exc_info:
            adapter.build_config_from_operator_params(
                connection_params=connection_params, credentials=credentials, provider_metadata=provider_metadata
            )

        assert "client_id" in str(exc_info.value)

    def test_build_config_missing_drive_id(self):
        """Test that missing drive_id defaults to 'url-based' for URL-based lookups."""
        adapter = SharePointACLAdapter()

        connection_params: dict[str, str] = {}
        credentials = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # pragma: allowlist secret
            "tenant_id": "test-tenant-id",
        }
        provider_metadata: dict[str, str] = {}

        config = adapter.build_config_from_operator_params(
            connection_params=connection_params, credentials=credentials, provider_metadata=provider_metadata
        )

        assert config.drive_id == "url-based"


class TestExtractACL:
    """Test ACL extraction functionality."""

    @pytest.mark.asyncio
    async def test_extract_acl_success(
        self, mock_acl_request, sharepoint_config_dict, mock_sharepoint_graph_response, mock_sharepoint_token_response
    ):
        """Test successful ACL extraction."""
        adapter = SharePointACLAdapter()

        with patch.object(adapter, "build_config_from_operator_params") as mock_build_config:
            mock_build_config.return_value = SharePointACLConfig(**sharepoint_config_dict)

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                with patch.object(adapter, "_fetch_permissions") as mock_fetch_perms:
                    mock_fetch_perms.return_value = [
                        RawPermission(
                            principal_id="user1@example.com",
                            principal_type="user",
                            principal_name="User One",
                            role="read",
                            permission_type="allow",
                            is_inherited=False,
                            inherited_from=None,
                            metadata={},
                        )
                    ]

                    response = await adapter.extract_acl(request=mock_acl_request)

                    assert isinstance(response, ACLResponse)
                    assert response.extraction_success is True
                    assert len(response.allowed_users) > 0
                    assert "user1@example.com" in response.allowed_users

    @pytest.mark.asyncio
    async def test_extract_acl_with_group_expansion(self, mock_acl_request, sharepoint_config_dict):
        """Test ACL extraction with group expansion."""
        adapter = SharePointACLAdapter()

        with patch.object(adapter, "build_config_from_operator_params") as mock_build_config:
            mock_build_config.return_value = SharePointACLConfig(**sharepoint_config_dict)

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                with patch.object(adapter, "_fetch_permissions") as mock_fetch_perms:
                    mock_fetch_perms.return_value = [
                        RawPermission(
                            principal_id="group-id-1",
                            principal_type="group",
                            principal_name="Test Group",
                            role="read",
                            permission_type="allow",
                            is_inherited=False,
                            inherited_from=None,
                            metadata={},
                        )
                    ]

                    with patch.object(adapter, "expand_group") as mock_expand:
                        mock_expand.return_value = {"user1@example.com", "user2@example.com"}

                        response = await adapter.extract_acl(request=mock_acl_request)

                        assert response.extraction_success is True
                        assert "user1@example.com" in response.allowed_users
                        assert "user2@example.com" in response.allowed_users
                        mock_expand.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_acl_with_inheritance_resolution(self, mock_acl_request, sharepoint_config_dict):
        """Test ACL extraction with inheritance resolution."""
        adapter = SharePointACLAdapter()

        with patch.object(adapter, "build_config_from_operator_params") as mock_build_config:
            mock_build_config.return_value = SharePointACLConfig(**sharepoint_config_dict)

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                with patch.object(adapter, "_fetch_permissions") as mock_fetch_perms:
                    mock_fetch_perms.return_value = []

                    with patch.object(adapter, "resolve_inheritance") as mock_resolve:
                        mock_resolve.return_value = ["item-id-1", "folder-id-1", "library-id-1"]

                        response = await adapter.extract_acl(request=mock_acl_request)

                        assert response.extraction_success is True
                        assert len(response.inheritance_chain) == 3
                        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_acl_missing_dependency(self, mock_acl_request, sharepoint_config_dict):
        """Test ACL extraction with missing msal dependency logs warning and returns empty permissions."""
        adapter = SharePointACLAdapter()

        with patch.object(adapter, "build_config_from_operator_params") as mock_build_config:
            mock_build_config.return_value = SharePointACLConfig(**sharepoint_config_dict)

            with patch.object(adapter, "_get_token") as mock_get_token:
                # Simulate missing msal dependency
                mock_get_token.side_effect = ConfigurationError("msal package not found")

                # Adapter is resilient - returns success with empty permissions and logs warning
                response = await adapter.extract_acl(request=mock_acl_request)

                assert isinstance(response, ACLResponse)
                assert response.extraction_success is True  # Adapter doesn't fail, just returns empty
                assert len(response.allowed_users) == 0
                assert response.resolution_metadata["raw_permission_count"] == 0


class TestResolveInheritance:
    """Test inheritance resolution."""

    @pytest.mark.asyncio
    async def test_resolve_inheritance_success(self, sharepoint_config_dict):
        """Test successful inheritance resolution."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch.object(adapter, "_create_rest_client") as mock_create_client:
            mock_rest_client = Mock()
            mock_rest_client.call_rest_json.side_effect = [
                {"parentReference": {"id": "folder-id-1"}},
                {"parentReference": {"id": "library-id-1"}},
                {},  # Root has no parent
            ]
            mock_create_client.return_value = mock_rest_client

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                chain = await adapter.resolve_inheritance(resource_id="item-id-1", resource_type="file", config=config)

                assert len(chain) == 3
                assert chain[0] == "item-id-1"
                assert chain[1] == "folder-id-1"
                assert chain[2] == "library-id-1"

    @pytest.mark.asyncio
    async def test_resolve_inheritance_circular_reference(self, sharepoint_config_dict):
        """Test inheritance resolution stops on circular reference."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch.object(adapter, "_create_rest_client") as mock_create_client:
            mock_rest_client = Mock()
            mock_rest_client.call_rest_json.side_effect = [
                {"parentReference": {"id": "folder-id-1"}},
                {"parentReference": {"id": "item-id-1"}},  # Circular reference
            ]
            mock_create_client.return_value = mock_rest_client

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                chain = await adapter.resolve_inheritance(resource_id="item-id-1", resource_type="file", config=config)

                # Should stop when circular reference detected
                assert len(chain) == 2


class TestExpandGroup:
    """Test group expansion."""

    @pytest.mark.asyncio
    async def test_expand_group_success(self, sharepoint_config_dict, mock_sharepoint_group_members):
        """Test successful group expansion."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch.object(adapter, "_create_rest_client") as mock_create_client:
            mock_rest_client = Mock()
            mock_rest_client.call_rest_json.return_value = mock_sharepoint_group_members
            mock_create_client.return_value = mock_rest_client

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                members = await adapter.expand_group(group_id="group-id-1", config=config)

                assert len(members) == 2
                assert "user3@example.com" in members
                assert "user4@example.com" in members

    @pytest.mark.asyncio
    async def test_expand_group_caching(self, sharepoint_config_dict, mock_sharepoint_group_members):
        """Test group expansion uses caching."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch.object(adapter, "_create_rest_client") as mock_create_client:
            mock_rest_client = Mock()
            mock_rest_client.call_rest_json.return_value = mock_sharepoint_group_members
            mock_create_client.return_value = mock_rest_client

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                # First call
                members1 = await adapter.expand_group(group_id="group-id-1", config=config)

                # Second call should use cache
                members2 = await adapter.expand_group(group_id="group-id-1", config=config)

                assert members1 == members2
                # Should only call API once
                assert mock_rest_client.call_rest_json.call_count == 1

    @pytest.mark.asyncio
    async def test_expand_group_pagination(self, sharepoint_config_dict):
        """Test group expansion handles pagination."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch.object(adapter, "_create_rest_client") as mock_create_client:
            mock_rest_client = Mock()
            mock_rest_client.call_rest_json.side_effect = [
                {
                    "value": [{"@odata.type": "#microsoft.graph.user", "userPrincipalName": "user1@example.com"}],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/groups/group-id-1/transitiveMembers?$skip=1",
                },
                {"value": [{"@odata.type": "#microsoft.graph.user", "userPrincipalName": "user2@example.com"}]},
            ]
            mock_create_client.return_value = mock_rest_client

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                members = await adapter.expand_group(group_id="group-id-1", config=config)

                assert len(members) == 2
                assert mock_rest_client.call_rest_json.call_count == 2


class TestNormalizeIdentity:
    """Test identity normalization."""

    def test_normalize_claims_format(self, sharepoint_config_dict):
        """Test normalization of SharePoint claims format."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        identity = "i:0#.f|membership|user@example.com"
        normalized = adapter.normalize_identity(principal_id=identity, principal_type="user", config=config)

        assert normalized == "user@example.com"

    def test_normalize_aad_format(self, sharepoint_config_dict):
        """Test normalization of AAD format."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        identity = "i:0#.f|aad|12345678-1234-1234-1234-123456789abc"
        normalized = adapter.normalize_identity(principal_id=identity, principal_type="user", config=config)

        # Should extract GUID (lowercase)
        assert "12345678-1234-1234-1234-123456789abc" in normalized

    def test_normalize_windows_format(self, sharepoint_config_dict):
        """Test normalization of Windows format."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        identity = "i:0#.w|domain\\username"
        normalized = adapter.normalize_identity(principal_id=identity, principal_type="user", config=config)

        assert normalized == "username"

    def test_normalize_email_format(self, sharepoint_config_dict):
        """Test normalization of email format."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        identity = "User@Example.COM"
        normalized = adapter.normalize_identity(principal_id=identity, principal_type="user", config=config)

        assert normalized == "user@example.com"

    def test_normalize_identity_caching(self, sharepoint_config_dict):
        """Test identity normalization uses caching."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        identity = "user@example.com"

        # First call
        normalized1 = adapter.normalize_identity(principal_id=identity, principal_type="user", config=config)

        # Second call should use cache
        normalized2 = adapter.normalize_identity(principal_id=identity, principal_type="user", config=config)

        assert normalized1 == normalized2
        assert identity.lower() in adapter._identity_cache


class TestTestConnection:
    """Test connection testing."""

    @pytest.mark.asyncio
    async def test_connection_success(self, sharepoint_config_dict):
        """Test successful connection test."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch.object(adapter, "_create_rest_client") as mock_create_client:
            mock_rest_client = Mock()
            mock_rest_client.call_rest_json.return_value = {"id": "test-drive-id"}
            mock_create_client.return_value = mock_rest_client

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                result = await adapter.test_connection(config=config)

                assert result is True

    @pytest.mark.asyncio
    async def test_connection_failure(self, sharepoint_config_dict):
        """Test failed connection test."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch.object(adapter, "_create_rest_client") as mock_create_client:
            mock_rest_client = Mock()
            mock_rest_client.call_rest_json.side_effect = Exception("Connection failed")
            mock_create_client.return_value = mock_rest_client

            with patch.object(adapter, "_get_token") as mock_get_token:
                mock_get_token.return_value = "mock-token"

                result = await adapter.test_connection(config=config)

                assert result is False


class TestGetToken:
    """Test OAuth token acquisition."""

    @pytest.mark.asyncio
    async def test_get_token_success(self, sharepoint_config_dict, mock_sharepoint_token_response):
        """Test successful token acquisition."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch("msal.ConfidentialClientApplication") as mock_msal:
            mock_app = Mock()
            mock_app.acquire_token_for_client.return_value = mock_sharepoint_token_response
            mock_msal.return_value = mock_app

            token = await adapter._get_token(config=config)

            assert token == "mock-access-token-12345"

    @pytest.mark.asyncio
    async def test_get_token_caching(self, sharepoint_config_dict, mock_sharepoint_token_response):
        """Test token caching."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch("msal.ConfidentialClientApplication") as mock_msal:
            mock_app = Mock()
            mock_app.acquire_token_for_client.return_value = mock_sharepoint_token_response
            mock_msal.return_value = mock_app

            # First call
            token1 = await adapter._get_token(config=config)

            # Second call should use cache
            token2 = await adapter._get_token(config=config)

            assert token1 == token2
            # Should only call MSAL once
            assert mock_app.acquire_token_for_client.call_count == 1

    @pytest.mark.asyncio
    async def test_get_token_failure(self, sharepoint_config_dict):
        """Test token acquisition failure."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with patch("msal.ConfidentialClientApplication") as mock_msal:
            mock_app = Mock()
            mock_app.acquire_token_for_client.return_value = {
                "error": "invalid_client",
                "error_description": "Invalid client credentials",
            }
            mock_msal.return_value = mock_app

            with pytest.raises(ExternalServiceError) as exc_info:
                await adapter._get_token(config=config)

            assert "Failed to acquire" in str(exc_info.value)


class TestExtractItemId:
    """Test item ID extraction."""

    @pytest.mark.asyncio
    async def test_extract_item_id_from_metadata(self, sharepoint_config_dict):
        """Test extracting item ID from metadata."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        item_id = await adapter._extract_item_id(
            config=config,
            resource_id="test-item-id",
            resource_path="/path/to/file",
            provider_metadata={"item_id": "test-item-id"},
        )

        assert item_id == "test-item-id"

    @pytest.mark.asyncio
    async def test_extract_item_id_from_path(self, sharepoint_config_dict):
        """Test extracting item ID from path."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        item_id = await adapter._extract_item_id(
            config=config,
            resource_id="item-id-123",
            resource_path="/drives/drive-id/items/item-id-123",
            provider_metadata={},
        )

        assert item_id == "item-id-123"

    @pytest.mark.asyncio
    async def test_extract_item_id_failure(self, sharepoint_config_dict):
        """Test item ID extraction failure."""
        adapter = SharePointACLAdapter()
        config = SharePointACLConfig(**sharepoint_config_dict)

        with pytest.raises(ConfigurationError) as exc_info:
            await adapter._extract_item_id(
                config=config, resource_id="", resource_path="/invalid/path", provider_metadata={}
            )

        assert "Could not extract" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
