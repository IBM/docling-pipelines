"""Unit tests for Flow DTO validation."""

from datetime import UTC

import pytest
from pydantic import ValidationError

from datasift.api.dto.flow_dto import (
    FlowCreateRequest,
    FlowResponse,
    FlowUpdateRequest,
    PaginatedFlowResponse,
)


class TestFlowCreateRequestValidation:
    """Tests for FlowCreateRequest DTO validation."""

    def test_create_request_with_valid_minimal_data(self):
        """Test creating request with only required fields."""
        # Arrange & Act
        dto = FlowCreateRequest(name="Test Flow")

        # Assert
        assert dto.name == "Test Flow"
        assert dto.description is None
        assert dto.definition is None
        assert dto.tags == []
        assert dto.is_hidden is False
        assert dto.flow_version == "2.0"

    def test_create_request_with_all_fields(self):
        """Test creating request with all fields."""
        # Arrange & Act
        dto = FlowCreateRequest(
            name="Test Flow",
            description="Test description",
            definition={
                "flow": {
                    "dag": [
                        {
                            "id": "node1",
                            "operator": "ingest_local",
                            "operator_params": {"path": "/data"},
                        }
                    ],
                    "global_config": {},
                }
            },
            tags=["tag1", "tag2"],
            container_kind="project",
            container_id="550e8400-e29b-41d4-a716-446655440000",
            is_hidden=True,
            flow_version="2.0",
            job_id="660e8400-e29b-41d4-a716-446655440000",
            created_by="test_user",
        )

        # Assert
        assert dto.name == "Test Flow"
        assert dto.description == "Test description"
        assert dto.tags == ["tag1", "tag2"]
        assert dto.container_kind == "project"
        assert dto.is_hidden is True

    def test_create_request_with_empty_name_raises_error(self):
        """Test that empty name raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowCreateRequest(name="")

        assert "name" in str(exc_info.value)

    def test_create_request_with_name_exceeding_256_chars_raises_error(self):
        """Test that name exceeding 256 characters raises validation error."""
        # Arrange
        long_name = "x" * 257

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowCreateRequest(name=long_name)

        assert "name" in str(exc_info.value)

    def test_create_request_with_description_exceeding_10000_chars_raises_error(self):
        """Test that description exceeding 10000 characters raises validation error."""
        # Arrange
        long_description = "x" * 10001

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowCreateRequest(name="Test", description=long_description)

        assert "description" in str(exc_info.value)

    def test_create_request_with_tag_max_length_256_valid(self):
        """Test that tag with exactly 256 characters is valid."""
        # Arrange
        tag_256 = "x" * 256

        # Act
        dto = FlowCreateRequest(name="Test", tags=[tag_256])

        # Assert
        assert len(dto.tags[0]) == 256

    def test_create_request_with_too_many_tags_raises_error(self):
        """Test that more than 36 tags raises validation error."""
        # Arrange
        too_many_tags = [f"tag{i}" for i in range(37)]

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowCreateRequest(name="Test", tags=too_many_tags)

        assert "tags" in str(exc_info.value)

    def test_create_request_with_container_kind_exceeding_7_chars_raises_error(self):
        """Test that container_kind exceeding 7 characters raises validation error."""
        # Arrange
        long_kind = "x" * 8

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowCreateRequest(name="Test", container_kind=long_kind)

        assert "container_kind" in str(exc_info.value)

    def test_create_request_with_empty_string_description(self):
        """Test that description accepts empty string (min_length=0)."""
        # Act
        dto = FlowCreateRequest(name="Test", description="")

        # Assert
        assert dto.name == "Test"
        assert dto.description == ""

    def test_create_request_with_invalid_container_kind_raises_error(self):
        """Test that invalid container_kind raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowCreateRequest(name="Test", container_kind="invalid")

        assert "container_kind" in str(exc_info.value)

    def test_create_request_with_valid_container_kind_project(self):
        """Test that 'project' container_kind is valid."""
        # Act
        dto = FlowCreateRequest(name="Test", container_kind="project")

        # Assert
        assert dto.container_kind == "project"

    def test_create_request_with_valid_container_kind_space(self):
        """Test that 'space' container_kind is valid."""
        # Act
        dto = FlowCreateRequest(name="Test", container_kind="space")

        # Assert
        assert dto.container_kind == "space"

    def test_create_request_with_invalid_container_id_raises_error(self):
        """Test that invalid UUID for container_id raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowCreateRequest(name="Test", container_id="not-a-uuid")

        assert "container_id" in str(exc_info.value)

    def test_create_request_with_valid_container_id(self):
        """Test that valid UUID for container_id is accepted."""
        # Act
        dto = FlowCreateRequest(name="Test", container_id="550e8400-e29b-41d4-a716-446655440000")

        # Assert
        assert dto.container_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_create_request_with_invalid_job_id_raises_error(self):
        """Test that invalid UUID for job_id raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowCreateRequest(name="Test", job_id="not-a-uuid")

        assert "job_id" in str(exc_info.value)

    def test_create_request_with_valid_job_id(self):
        """Test that valid UUID for job_id is accepted."""
        # Act
        dto = FlowCreateRequest(name="Test", job_id="660e8400-e29b-41d4-a716-446655440000")

        # Assert
        assert dto.job_id == "660e8400-e29b-41d4-a716-446655440000"

    def test_create_request_with_definition_containing_doc_type(self):
        """Test that definition with doc_type (Elyra format) is valid."""
        # Act
        dto = FlowCreateRequest(
            name="Test",
            definition={
                "doc_type": "pipeline",
                "version": "3.0",
                "pipelines": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "nodes": [],
                        "app_data": {"ui_data": {}, "version": 3.0},
                    }
                ],
                "schemas": [],
            },
        )

        # Assert
        assert dto.definition is not None
        assert dto.definition["doc_type"] == "pipeline"
        assert "pipelines" in dto.definition

    def test_create_request_with_definition_containing_nodes(self):
        """Test that definition with nodes (Internal DAG format) is valid."""
        # Act
        dto = FlowCreateRequest(
            name="Test",
            definition={
                "flow": {
                    "dag": [
                        {
                            "id": "node1",
                            "operator": "ingest_local",
                            "operator_params": {"path": "/data"},
                        }
                    ],
                    "global_config": {},
                }
            },
        )

        # Assert
        assert dto.definition is not None
        assert "flow" in dto.definition
        assert "dag" in dto.definition["flow"]
        assert len(dto.definition["flow"]["dag"]) == 1

    def test_create_request_with_invalid_definition_raises_error(self):
        """Test that definition without doc_type or nodes raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowCreateRequest(name="Test", definition={"invalid": "structure"})

        assert "definition" in str(exc_info.value)

    def test_create_request_deduplicates_tags(self):
        """Test that duplicate tags are removed."""
        # Act
        dto = FlowCreateRequest(name="Test", tags=["tag1", "tag2", "tag1", "tag3", "tag2"])

        # Assert
        assert dto.tags == ["tag1", "tag2", "tag3"]

    def test_create_request_preserves_tag_order(self):
        """Test that tag order is preserved during deduplication."""
        # Act
        dto = FlowCreateRequest(name="Test", tags=["zebra", "alpha", "beta", "alpha"])

        # Assert
        assert dto.tags == ["zebra", "alpha", "beta"]


class TestFlowUpdateRequestValidation:
    """Tests for FlowUpdateRequest DTO validation."""

    def test_update_request_with_all_fields_optional(self):
        """Test that all fields are optional in update request."""
        # Act
        dto = FlowUpdateRequest()  # type: ignore

        # Assert
        assert dto.name is None
        assert dto.description is None
        assert dto.definition is None
        assert dto.tags is None
        assert dto.is_hidden is None

    def test_update_request_with_name_only(self):
        """Test updating only name field."""
        # Act
        dto = FlowUpdateRequest(name="Updated Name")  # type: ignore

        # Assert
        assert dto.name == "Updated Name"
        assert dto.description is None

    def test_update_request_with_empty_name_raises_error(self):
        """Test that empty name raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowUpdateRequest(name="")  # type: ignore

        assert "name" in str(exc_info.value)

    def test_update_request_with_invalid_container_kind_raises_error(self):
        """Test that invalid container_kind raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowUpdateRequest(container_kind="invalid")  # type: ignore

        assert "container_kind" in str(exc_info.value)

    def test_update_request_with_valid_container_kind(self):
        """Test that valid container_kind is accepted."""
        # Act
        dto = FlowUpdateRequest(container_kind="project")  # type: ignore

        # Assert
        assert dto.container_kind == "project"

    def test_update_request_with_invalid_definition_raises_error(self):
        """Test that invalid definition raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            FlowUpdateRequest(definition={"invalid": "structure"})  # type: ignore

        assert "definition" in str(exc_info.value)

    def test_update_request_deduplicates_tags(self):
        """Test that duplicate tags are removed in update request."""
        # Act
        dto = FlowUpdateRequest(tags=["tag1", "tag2", "tag1"])  # type: ignore

        # Assert
        assert dto.tags == ["tag1", "tag2"]


class TestFlowResponseValidation:
    """Tests for FlowResponse DTO validation."""

    def test_response_with_all_required_fields(self):
        """Test creating response with all required fields."""
        # Arrange
        from datetime import datetime

        # Act
        dto = FlowResponse(  # type: ignore
            flow_id="test-id",
            name="Test Flow",
            definition={"nodes": []},
            tags=[],
            created_on=datetime.now(UTC),
            modified_on=datetime.now(UTC),
        )

        # Assert
        assert dto.flow_id == "test-id"
        assert dto.name == "Test Flow"
        assert dto.tags == []
        assert dto.is_hidden is False
        assert dto.flow_version == "2.0"

    def test_response_with_all_fields(self):
        """Test creating response with all fields."""
        # Arrange
        from datetime import datetime

        # Act
        dto = FlowResponse(
            flow_id="test-id",
            name="Test Flow",
            description="Test description",
            definition={"nodes": []},
            tags=["tag1"],
            container_kind="project",
            container_id="550e8400-e29b-41d4-a716-446655440000",
            is_hidden=True,
            flow_version="2.0",
            created_on=datetime.now(UTC),
            modified_on=datetime.now(UTC),
            job_id="660e8400-e29b-41d4-a716-446655440000",
            created_by="user1",
            modified_by="user2",
            href="/api/flows/test-id",
        )

        # Assert
        assert dto.flow_id == "test-id"
        assert dto.description == "Test description"
        assert dto.container_kind == "project"
        assert dto.is_hidden is True


class TestPaginatedFlowResponseValidation:
    """Tests for PaginatedFlowResponse DTO validation."""

    def test_paginated_response_with_empty_flows(self):
        """Test creating paginated response with empty flows list."""
        # Act
        dto = PaginatedFlowResponse(flows=[], total_count=0, offset=0, limit=10)

        # Assert
        assert dto.flows == []
        assert dto.total_count == 0
        assert dto.offset == 0
        assert dto.limit == 10

    def test_paginated_response_with_flows(self):
        """Test creating paginated response with flows."""
        # Arrange
        from datetime import datetime

        flow_response = FlowResponse(  # type: ignore
            flow_id="test-id",
            name="Test Flow",
            definition={
                "nodes": [
                    {
                        "id": "node1",
                        "operator": "ingest_local",
                        "operator_params": {"path": "/data"},
                    }
                ],
            },
            tags=[],
            created_on=datetime.now(UTC),
            modified_on=datetime.now(UTC),
        )

        # Act
        dto = PaginatedFlowResponse(flows=[flow_response], total_count=1, offset=0, limit=10)

        # Assert
        assert len(dto.flows) == 1
        assert dto.total_count == 1

    def test_paginated_response_with_pagination_links(self):
        """Test paginated response with pagination links."""
        # Act
        dto = PaginatedFlowResponse(
            flows=[],
            total_count=150,
            offset=10,
            limit=10,
            first="http://api.example.com/v1/flows?offset=0&limit=10",
            next="http://api.example.com/v1/flows?offset=20&limit=10",
            prev="http://api.example.com/v1/flows?offset=0&limit=10",
        )

        # Assert
        assert dto.total_count == 150
        assert dto.offset == 10
        assert dto.first is not None
        assert dto.next is not None
        assert dto.prev is not None


class TestFlowDTOEdgeCases:
    """Tests for edge cases in Flow DTOs."""

    def test_create_request_with_none_tags_becomes_empty_list(self):
        """Test that None tags becomes empty list."""
        # Act
        dto = FlowCreateRequest(name="Test", tags=None)

        # Assert
        assert dto.tags == []

    def test_create_request_with_unicode_name(self):
        """Test that unicode characters in name are accepted."""
        # Act
        dto = FlowCreateRequest(name="Test Flow 测试 🚀")

        # Assert
        assert "测试" in dto.name
        assert "🚀" in dto.name

    def test_create_request_with_very_long_valid_name(self):
        """Test that name with exactly 256 characters is valid."""
        # Arrange
        name_256 = "x" * 256

        # Act
        dto = FlowCreateRequest(name=name_256)

        # Assert
        assert len(dto.name) == 256

    def test_update_request_dict_exclude_unset(self):
        """Test that dict(exclude_unset=True) only includes set fields."""
        # Act
        dto = FlowUpdateRequest(name="Updated")  # type: ignore
        result = dto.dict(exclude_unset=True)

        # Assert
        assert "name" in result
        assert "description" not in result
        assert "tags" not in result
