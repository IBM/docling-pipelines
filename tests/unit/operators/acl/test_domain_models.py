"""Unit tests for ACL domain models."""

import pytest

from docpipe.core.operators.acl.domain.models import (
    ACLExtractionResult,
    ACLRequest,
    ACLResponse,
    RawPermission,
)


class TestACLRequest:
    """Test ACLRequest domain model."""

    def test_create_acl_request_with_required_fields(self):
        """Test creating ACL request with required fields."""
        request = ACLRequest(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            resource_type="file",
            provider="sharepoint",
        )

        assert request.resource_id == "test-resource-id"
        assert request.resource_path == "/path/to/resource"
        assert request.resource_type == "file"
        assert request.provider == "sharepoint"

    def test_create_acl_request_with_default_values(self):
        """Test ACL request uses default values for optional fields."""
        request = ACLRequest(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            resource_type="file",
            provider="sharepoint",
        )

        assert request.provider_metadata == {}
        assert request.credentials == {}
        assert request.connection_params == {}
        assert request.resolve_inheritance is True
        assert request.expand_groups is True
        assert request.normalize_identities is True

    def test_create_acl_request_with_custom_values(self):
        """Test creating ACL request with custom values."""
        request = ACLRequest(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            resource_type="file",
            provider="sharepoint",
            provider_metadata={"site_url": "https://example.com"},
            credentials={"api_key": "test-key"},  # pragma: allowlist secret
            connection_params={"timeout": 30},
            resolve_inheritance=False,
            expand_groups=False,
            normalize_identities=False,
        )

        assert request.provider_metadata == {"site_url": "https://example.com"}
        assert request.credentials == {"api_key": "test-key"}  # pragma: allowlist secret
        assert request.connection_params == {"timeout": 30}
        assert request.resolve_inheritance is False
        assert request.expand_groups is False
        assert request.normalize_identities is False

    def test_acl_request_is_dataclass(self):
        """Test ACL request is a dataclass."""
        request = ACLRequest(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            resource_type="file",
            provider="sharepoint",
        )

        # Dataclasses have __dataclass_fields__
        assert hasattr(request, "__dataclass_fields__")


class TestACLResponse:
    """Test ACLResponse domain model."""

    def test_create_acl_response_with_required_fields(self):
        """Test creating ACL response with required fields."""
        response = ACLResponse(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            allowed_users={"user1@example.com", "user2@example.com"},
        )

        assert response.resource_id == "test-resource-id"
        assert response.resource_path == "/path/to/resource"
        assert len(response.allowed_users) == 2
        assert "user1@example.com" in response.allowed_users

    def test_create_acl_response_with_default_values(self):
        """Test ACL response uses default values for optional fields."""
        response = ACLResponse(resource_id="test-resource-id", resource_path="/path/to/resource", allowed_users=set())

        assert response.denied_users is None
        assert response.inheritance_chain == []
        assert response.has_unique_permissions is False
        assert response.resolution_metadata == {}
        assert response.extraction_success is True
        assert response.extraction_error is None
        assert response.extraction_warnings == []

    def test_create_acl_response_with_custom_values(self):
        """Test creating ACL response with custom values."""
        response = ACLResponse(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            allowed_users={"user1@example.com"},
            denied_users={"user2@example.com"},
            inheritance_chain=["item-1", "folder-1", "library-1"],
            has_unique_permissions=True,
            resolution_metadata={"groups_expanded": 2},
            extraction_success=False,
            extraction_error="Authentication failed",
            extraction_warnings=["Warning 1", "Warning 2"],
        )

        assert response.denied_users == {"user2@example.com"}
        assert len(response.inheritance_chain) == 3
        assert response.has_unique_permissions is True
        assert response.resolution_metadata == {"groups_expanded": 2}
        assert response.extraction_success is False
        assert response.extraction_error == "Authentication failed"
        assert len(response.extraction_warnings) == 2

    def test_get_all_users_with_allowed_only(self):
        """Test get_all_users with only allowed users."""
        response = ACLResponse(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            allowed_users={"user1@example.com", "user2@example.com"},
        )

        all_users = response.get_all_users()

        assert len(all_users) == 2
        assert "user1@example.com" in all_users
        assert "user2@example.com" in all_users

    def test_get_all_users_with_allowed_and_denied(self):
        """Test get_all_users with both allowed and denied users."""
        response = ACLResponse(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            allowed_users={"user1@example.com", "user2@example.com"},
            denied_users={"user3@example.com", "user4@example.com"},
        )

        all_users = response.get_all_users()

        assert len(all_users) == 4
        assert "user1@example.com" in all_users
        assert "user2@example.com" in all_users
        assert "user3@example.com" in all_users
        assert "user4@example.com" in all_users

    def test_get_all_users_no_duplicates(self):
        """Test get_all_users removes duplicates."""
        response = ACLResponse(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            allowed_users={"user1@example.com", "user2@example.com"},
            denied_users={"user2@example.com", "user3@example.com"},
        )

        all_users = response.get_all_users()

        # Should have 3 unique users
        assert len(all_users) == 3

    def test_acl_response_allowed_users_is_set(self):
        """Test allowed_users is a set."""
        response = ACLResponse(
            resource_id="test-resource-id", resource_path="/path/to/resource", allowed_users={"user1@example.com"}
        )

        assert isinstance(response.allowed_users, set)


class TestACLExtractionResult:
    """Test ACLExtractionResult domain model."""

    def test_create_extraction_result_with_defaults(self):
        """Test creating extraction result with default values."""
        result = ACLExtractionResult()

        assert result.successful_extractions == []
        assert result.failed_extractions == []
        assert result.total_resources == 0
        assert result.success_count == 0
        assert result.failure_count == 0
        assert result.processing_time_seconds == 0.0
        assert result.cache_statistics == {}

    def test_create_extraction_result_with_custom_values(self):
        """Test creating extraction result with custom values."""
        successful = [
            ACLResponse(resource_id="resource-1", resource_path="/path/1", allowed_users={"user1@example.com"})
        ]
        failed = [{"resource_id": "resource-2", "error": "Authentication failed"}]

        result = ACLExtractionResult(
            successful_extractions=successful,
            failed_extractions=failed,
            total_resources=2,
            success_count=1,
            failure_count=1,
            processing_time_seconds=5.5,
            cache_statistics={"cache_hits": 10, "cache_misses": 2},
        )

        assert len(result.successful_extractions) == 1
        assert len(result.failed_extractions) == 1
        assert result.total_resources == 2
        assert result.success_count == 1
        assert result.failure_count == 1
        assert result.processing_time_seconds == 5.5
        assert result.cache_statistics["cache_hits"] == 10

    def test_extraction_result_lists_are_mutable(self):
        """Test extraction result lists can be modified."""
        result = ACLExtractionResult()

        # Should be able to append to lists
        result.successful_extractions.append(
            ACLResponse(resource_id="resource-1", resource_path="/path/1", allowed_users=set())
        )

        assert len(result.successful_extractions) == 1


class TestRawPermission:
    """Test RawPermission domain model."""

    def test_create_raw_permission_with_required_fields(self):
        """Test creating raw permission with required fields."""
        permission = RawPermission(principal_id="user1@example.com", principal_type="user", principal_name="User One")

        assert permission.principal_id == "user1@example.com"
        assert permission.principal_type == "user"
        assert permission.principal_name == "User One"

    def test_create_raw_permission_with_default_values(self):
        """Test raw permission uses default values for optional fields."""
        permission = RawPermission(principal_id="user1@example.com", principal_type="user")

        assert permission.principal_name is None
        assert permission.role is None
        assert permission.permission_type is None
        assert permission.is_inherited is False
        assert permission.inherited_from is None
        assert permission.metadata == {}

    def test_create_raw_permission_with_custom_values(self):
        """Test creating raw permission with custom values."""
        permission = RawPermission(
            principal_id="user1@example.com",
            principal_type="user",
            principal_name="User One",
            role="read",
            permission_type="allow",
            is_inherited=True,
            inherited_from="folder-id-1",
            metadata={"source": "sharepoint"},
        )

        assert permission.role == "read"
        assert permission.permission_type == "allow"
        assert permission.is_inherited is True
        assert permission.inherited_from == "folder-id-1"
        assert permission.metadata == {"source": "sharepoint"}

    def test_raw_permission_principal_types(self):
        """Test raw permission with different principal types."""
        user_perm = RawPermission(principal_id="user1@example.com", principal_type="user")

        group_perm = RawPermission(principal_id="group-id-1", principal_type="group")

        link_perm = RawPermission(principal_id="link-id-1", principal_type="link")

        assert user_perm.principal_type == "user"
        assert group_perm.principal_type == "group"
        assert link_perm.principal_type == "link"

    def test_raw_permission_inheritance_fields(self):
        """Test raw permission inheritance-related fields."""
        inherited_perm = RawPermission(
            principal_id="user1@example.com",
            principal_type="user",
            is_inherited=True,
            inherited_from="parent-resource-id",
        )

        direct_perm = RawPermission(principal_id="user2@example.com", principal_type="user", is_inherited=False)

        assert inherited_perm.is_inherited is True
        assert inherited_perm.inherited_from == "parent-resource-id"
        assert direct_perm.is_inherited is False
        assert direct_perm.inherited_from is None


class TestDomainModelInteractions:
    """Test interactions between domain models."""

    def test_acl_request_to_response_flow(self):
        """Test typical flow from request to response."""
        # Create request
        request = ACLRequest(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            resource_type="file",
            provider="sharepoint",
            resolve_inheritance=True,
            expand_groups=True,
        )

        # Create response based on request
        response = ACLResponse(
            resource_id=request.resource_id,
            resource_path=request.resource_path,
            allowed_users={"user1@example.com", "user2@example.com"},
            extraction_success=True,
        )

        assert response.resource_id == request.resource_id
        assert response.resource_path == request.resource_path
        assert response.extraction_success is True

    def test_raw_permission_to_acl_response_aggregation(self):
        """Test aggregating raw permissions into ACL response."""
        raw_permissions = [
            RawPermission(principal_id="user1@example.com", principal_type="user", permission_type="allow"),
            RawPermission(principal_id="user2@example.com", principal_type="user", permission_type="allow"),
            RawPermission(principal_id="user3@example.com", principal_type="user", permission_type="deny"),
        ]

        # Simulate processing raw permissions
        allowed_users = {perm.principal_id for perm in raw_permissions if perm.permission_type == "allow"}
        denied_users = {perm.principal_id for perm in raw_permissions if perm.permission_type == "deny"}

        response = ACLResponse(
            resource_id="test-resource-id",
            resource_path="/path/to/resource",
            allowed_users=allowed_users,
            denied_users=denied_users,
        )

        assert len(response.allowed_users) == 2
        assert len(response.denied_users) == 1

    def test_extraction_result_aggregation(self):
        """Test aggregating multiple responses into extraction result."""
        responses = [
            ACLResponse(
                resource_id=f"resource-{i}",
                resource_path=f"/path/{i}",
                allowed_users={"user@example.com"},
                extraction_success=True,
            )
            for i in range(3)
        ]

        result = ACLExtractionResult(
            successful_extractions=responses, total_resources=3, success_count=len(responses), failure_count=0
        )

        assert result.total_resources == 3
        assert result.success_count == 3
        assert result.failure_count == 0
        assert len(result.successful_extractions) == 3


class TestDomainModelEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_acl_response_empty_allowed_users(self):
        """Test ACL response with empty allowed users."""
        response = ACLResponse(resource_id="test-resource-id", resource_path="/path/to/resource", allowed_users=set())

        assert len(response.allowed_users) == 0
        assert isinstance(response.allowed_users, set)

    def test_acl_response_large_user_set(self):
        """Test ACL response with large number of users."""
        large_user_set = {f"user{i}@example.com" for i in range(1000)}

        response = ACLResponse(
            resource_id="test-resource-id", resource_path="/path/to/resource", allowed_users=large_user_set
        )

        assert len(response.allowed_users) == 1000

    def test_raw_permission_empty_metadata(self):
        """Test raw permission with empty metadata."""
        permission = RawPermission(principal_id="user1@example.com", principal_type="user", metadata={})

        assert permission.metadata == {}
        assert isinstance(permission.metadata, dict)

    def test_extraction_result_zero_resources(self):
        """Test extraction result with zero resources."""
        result = ACLExtractionResult(total_resources=0, success_count=0, failure_count=0)

        assert result.total_resources == 0
        assert result.success_count == 0
        assert result.failure_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
