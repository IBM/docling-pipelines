"""Unit tests for Flow DTO validation."""

from datetime import UTC

import pytest
from pydantic import ValidationError

from docpipe.api.dto.authoring_flow_dto import (
    AuthoringFlowCreateRequest,
    AuthoringOperatorDTO,
)
from docpipe.api.dto.flow_dto import (
    ElyraFlowCreateRequest,
    ElyraFlowUpdateRequest,
    FlowResponse,
    PaginatedFlowResponse,
)


class TestFlowCreateRequestValidation:
    """Tests for ElyraFlowCreateRequest DTO validation."""

    def test_create_request_with_valid_minimal_data(self):
        """Test creating request with only required fields."""
        # Arrange & Act
        dto = ElyraFlowCreateRequest(name="Test Flow")

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
        dto = ElyraFlowCreateRequest(
            name="Test Flow",
            description="Test description",
            definition={
                "doc_type": "pipeline",
                "version": "3.0",
                "pipelines": [
                    {
                        "id": "pipeline1",
                        "nodes": [
                            {
                                "id": "node1",
                                "type": "execution_node",
                                "op": "execute-notebook-node",
                            }
                        ],
                        "app_data": {"ui_data": {}, "version": 3.0},
                    }
                ],
                "schemas": [],
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
            ElyraFlowCreateRequest(name="")

        assert "name" in str(exc_info.value)

    def test_create_request_with_name_exceeding_256_chars_raises_error(self):
        """Test that name exceeding 256 characters raises validation error."""
        # Arrange
        long_name = "x" * 257

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowCreateRequest(name=long_name)

        assert "name" in str(exc_info.value)

    def test_create_request_with_description_exceeding_10000_chars_raises_error(self):
        """Test that description exceeding 10000 characters raises validation error."""
        # Arrange
        long_description = "x" * 10001

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowCreateRequest(name="Test", description=long_description)

        assert "description" in str(exc_info.value)

    def test_create_request_with_tag_max_length_256_valid(self):
        """Test that tag with exactly 256 characters is valid."""
        # Arrange
        tag_256 = "x" * 256

        # Act
        dto = ElyraFlowCreateRequest(name="Test", tags=[tag_256])

        # Assert
        assert len(dto.tags[0]) == 256

    def test_create_request_with_too_many_tags_raises_error(self):
        """Test that more than 36 tags raises validation error."""
        # Arrange
        too_many_tags = [f"tag{i}" for i in range(37)]

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowCreateRequest(name="Test", tags=too_many_tags)

        assert "tags" in str(exc_info.value)

    def test_create_request_with_container_kind_exceeding_7_chars_raises_error(self):
        """Test that container_kind exceeding 7 characters raises validation error."""
        # Arrange
        long_kind = "x" * 8

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowCreateRequest(name="Test", container_kind=long_kind)

        assert "container_kind" in str(exc_info.value)

    def test_create_request_with_empty_string_description(self):
        """Test that description accepts empty string (min_length=0)."""
        # Act
        dto = ElyraFlowCreateRequest(name="Test", description="")

        # Assert
        assert dto.name == "Test"
        assert dto.description == ""

    def test_create_request_with_invalid_container_kind_raises_error(self):
        """Test that invalid container_kind raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowCreateRequest(name="Test", container_kind="invalid")

        assert "container_kind" in str(exc_info.value)

    def test_create_request_with_valid_container_kind_project(self):
        """Test that 'project' container_kind is valid."""
        # Act
        dto = ElyraFlowCreateRequest(name="Test", container_kind="project")

        # Assert
        assert dto.container_kind == "project"

    def test_create_request_with_valid_container_kind_space(self):
        """Test that 'space' container_kind is valid."""
        # Act
        dto = ElyraFlowCreateRequest(name="Test", container_kind="space")

        # Assert
        assert dto.container_kind == "space"

    def test_create_request_with_invalid_container_id_raises_error(self):
        """Test that invalid UUID for container_id raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowCreateRequest(name="Test", container_id="not-a-uuid")

        assert "container_id" in str(exc_info.value)

    def test_create_request_with_valid_container_id(self):
        """Test that valid UUID for container_id is accepted."""
        # Act
        dto = ElyraFlowCreateRequest(name="Test", container_id="550e8400-e29b-41d4-a716-446655440000")

        # Assert
        assert dto.container_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_create_request_with_invalid_job_id_raises_error(self):
        """Test that invalid UUID for job_id raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowCreateRequest(name="Test", job_id="not-a-uuid")

        assert "job_id" in str(exc_info.value)

    def test_create_request_with_valid_job_id(self):
        """Test that valid UUID for job_id is accepted."""
        # Act
        dto = ElyraFlowCreateRequest(name="Test", job_id="660e8400-e29b-41d4-a716-446655440000")

        # Assert
        assert dto.job_id == "660e8400-e29b-41d4-a716-446655440000"

    def test_create_request_with_definition_containing_doc_type(self):
        """Test that definition with doc_type (Elyra format) is valid."""
        # Act
        dto = ElyraFlowCreateRequest(
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
        """Test that definition with nodes (Elyra format) is valid."""
        # Act
        dto = ElyraFlowCreateRequest(
            name="Test",
            definition={
                "doc_type": "pipeline",
                "version": "3.0",
                "pipelines": [
                    {
                        "id": "pipeline1",
                        "nodes": [
                            {
                                "id": "node1",
                                "type": "execution_node",
                                "op": "ingest_source",
                                "parameters": {"path": "/data"},
                                "app_data": {"ui_data": {}},
                            }
                        ],
                        "app_data": {"ui_data": {}},
                    }
                ],
                "schemas": [],
            },
        )

        # Assert
        assert dto.definition is not None
        assert "doc_type" in dto.definition
        assert "pipelines" in dto.definition
        assert len(dto.definition["pipelines"]) == 1
        assert dto.definition["pipelines"][0]["nodes"][0]["parameters"]["path"] == "/data"

    def test_create_request_with_invalid_definition_raises_error(self):
        """Test that definition without doc_type or nodes raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowCreateRequest(name="Test", definition={"invalid": "structure"})

        assert "definition" in str(exc_info.value)

    def test_create_request_deduplicates_tags(self):
        """Test that duplicate tags are removed."""
        # Act
        dto = ElyraFlowCreateRequest(name="Test", tags=["tag1", "tag2", "tag1", "tag3", "tag2"])

        # Assert
        assert dto.tags == ["tag1", "tag2", "tag3"]

    def test_create_request_preserves_tag_order(self):
        """Test that tag order is preserved during deduplication."""
        # Act
        dto = ElyraFlowCreateRequest(name="Test", tags=["zebra", "alpha", "beta", "alpha"])

        # Assert
        assert dto.tags == ["zebra", "alpha", "beta"]


class TestFlowUpdateRequestValidation:
    """Tests for ElyraFlowUpdateRequest DTO validation."""

    def test_update_request_with_all_fields_optional(self):
        """Test that all fields are optional in update request."""
        # Act
        dto = ElyraFlowUpdateRequest()  # type: ignore

        # Assert
        assert dto.name is None
        assert dto.description is None
        assert dto.definition is None
        assert dto.tags is None
        assert dto.is_hidden is None

    def test_update_request_with_name_only(self):
        """Test updating only name field."""
        # Act
        dto = ElyraFlowUpdateRequest(name="Updated Name")  # type: ignore

        # Assert
        assert dto.name == "Updated Name"
        assert dto.description is None

    def test_update_request_with_empty_name_raises_error(self):
        """Test that empty name raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowUpdateRequest(name="")  # type: ignore

        assert "name" in str(exc_info.value)

    def test_update_request_with_invalid_container_kind_raises_error(self):
        """Test that invalid container_kind raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowUpdateRequest(container_kind="invalid")  # type: ignore

        assert "container_kind" in str(exc_info.value)

    def test_update_request_with_valid_container_kind(self):
        """Test that valid container_kind is accepted."""
        # Act
        dto = ElyraFlowUpdateRequest(container_kind="project")  # type: ignore

        # Assert
        assert dto.container_kind == "project"

    def test_update_request_with_invalid_definition_raises_error(self):
        """Test that invalid definition raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ElyraFlowUpdateRequest(definition={"invalid": "structure"})  # type: ignore

        assert "definition" in str(exc_info.value)

    def test_update_request_deduplicates_tags(self):
        """Test that duplicate tags are removed in update request."""
        # Act
        dto = ElyraFlowUpdateRequest(tags=["tag1", "tag2", "tag1"])  # type: ignore

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
                        "operator": "ingest_source",
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
        dto = ElyraFlowCreateRequest(name="Test", tags=None)  # type: ignore

        # Assert
        assert dto.tags == []

    def test_create_request_with_unicode_name(self):
        """Test that unicode characters in name are accepted."""
        # Act
        dto = ElyraFlowCreateRequest(name="Test Flow 测试 🚀")

        # Assert
        assert "测试" in dto.name
        assert "🚀" in dto.name

    def test_create_request_with_very_long_valid_name(self):
        """Test that name with exactly 256 characters is valid."""
        # Arrange
        name_256 = "x" * 256

        # Act
        dto = ElyraFlowCreateRequest(name=name_256)

        # Assert
        assert len(dto.name) == 256

    def test_update_request_dict_exclude_unset(self):
        """Test that dict(exclude_unset=True) only includes set fields."""
        # Act
        dto = ElyraFlowUpdateRequest(name="Updated")  # type: ignore
        result = dto.dict(exclude_unset=True)

        # Assert
        assert "name" in result
        assert "description" not in result
        assert "tags" not in result


class TestAuthoringOperatorDTOValidation:
    """Tests for AuthoringOperatorDTO validation."""

    def test_operator_minimal_and_complete_fields(self):
        """Test operator with minimal and complete field sets."""
        # Minimal
        minimal = AuthoringOperatorDTO(type="ingest_source", name="ingest")
        assert minimal.config == {}
        assert minimal.depends_on == []

        # Complete
        complete = AuthoringOperatorDTO(
            type="extract_operator",
            name="extract",
            config={"mode": "docling"},
            depends_on=["ingest"],
        )
        assert complete.config == {"mode": "docling"}
        assert complete.depends_on == ["ingest"]

    def test_operator_validation_errors(self):
        """Test operator field validation errors."""
        # Empty type
        with pytest.raises(ValidationError, match="type"):
            AuthoringOperatorDTO(type="", name="test")

        # Empty name
        with pytest.raises(ValidationError, match="name"):
            AuthoringOperatorDTO(type="ingest_source", name="")

        # Type too long (>256 chars)
        with pytest.raises(ValidationError, match="type"):
            AuthoringOperatorDTO(type="x" * 257, name="test")

        # Name too long (>256 chars)
        with pytest.raises(ValidationError, match="name"):
            AuthoringOperatorDTO(type="ingest_source", name="x" * 257)

    def test_operator_complex_config_and_dependencies(self):
        """Test operator with nested config and multiple dependencies."""
        dto = AuthoringOperatorDTO(
            type="vectordb",
            name="store",
            config={
                "provider": "opensearch",
                "provider_config": {"host": "localhost", "port": 9200},
            },
            depends_on=["path_a", "path_b", "classifier.branch"],
        )
        assert dto.config["provider_config"]["host"] == "localhost"
        assert len(dto.depends_on) == 3
        assert "classifier.branch" in dto.depends_on


class TestAuthoringFlowCreateRequestValidation:
    """Tests for AuthoringFlowCreateRequest DTO validation."""

    def test_flow_minimal_and_complete(self):
        """Test flow with minimal and complete configurations."""
        # Minimal
        minimal = AuthoringFlowCreateRequest(
            flow_name="simple",
            flow=[AuthoringOperatorDTO(type="ingest_source", name="ingest")],
        )
        assert minimal.description is None
        assert minimal.global_config == {}
        assert minimal.tags == []

        # Complete
        complete = AuthoringFlowCreateRequest(
            flow_name="complete-pipeline",
            description="Full pipeline",
            flow=[
                AuthoringOperatorDTO(type="ingest_source", name="ingest", config={"path": "./data"}),
                AuthoringOperatorDTO(type="extract_operator", name="extract", depends_on=["ingest"]),
            ],
            global_config={"doc_column": "content"},
            tags=["prod", "v1"],
        )
        assert len(complete.flow) == 2
        assert complete.flow[1].depends_on == ["ingest"]
        assert complete.global_config["doc_column"] == "content"

    def test_flow_validation_errors(self):
        """Test flow field validation errors."""
        # Empty flow_name
        with pytest.raises(ValidationError, match="flow_name"):
            AuthoringFlowCreateRequest(
                flow_name="",
                flow=[AuthoringOperatorDTO(type="ingest_source", name="ingest")],
            )

        # flow_name too long (>256 chars)
        with pytest.raises(ValidationError, match="flow_name"):
            AuthoringFlowCreateRequest(
                flow_name="x" * 257,
                flow=[AuthoringOperatorDTO(type="ingest_source", name="ingest")],
            )

        # Empty flow list
        with pytest.raises(ValidationError, match="flow"):
            AuthoringFlowCreateRequest(flow_name="test", flow=[])

        # Too many operators (>10000)
        with pytest.raises(ValidationError, match="flow"):
            AuthoringFlowCreateRequest(
                flow_name="test",
                flow=[AuthoringOperatorDTO(type="noop", name=f"op_{i}") for i in range(10001)],
            )

        # Description too long (>10000 chars)
        with pytest.raises(ValidationError, match="description"):
            AuthoringFlowCreateRequest(
                flow_name="test",
                description="x" * 10001,
                flow=[AuthoringOperatorDTO(type="ingest_source", name="ingest")],
            )

        # Too many tags (>36)
        with pytest.raises(ValidationError, match="tags"):
            AuthoringFlowCreateRequest(
                flow_name="test",
                flow=[AuthoringOperatorDTO(type="ingest_source", name="ingest")],
                tags=[f"tag{i}" for i in range(37)],
            )

    def test_flow_branching_and_merging(self):
        """Test flow with branching and merge operators."""
        dto = AuthoringFlowCreateRequest(
            flow_name="branch-merge",
            flow=[
                AuthoringOperatorDTO(type="ingest_source", name="ingest"),
                AuthoringOperatorDTO(
                    type="branching",
                    name="classify",
                    depends_on=["ingest"],
                    config={
                        "branches": {
                            "invoices": {"condition": "type == 'invoice'"},
                            "receipts": {"condition": "type == 'receipt'"},
                        }
                    },
                ),
                AuthoringOperatorDTO(type="extract_operator", name="proc_inv", depends_on=["classify.invoices"]),
                AuthoringOperatorDTO(type="extract_operator", name="proc_rec", depends_on=["classify.receipts"]),
                AuthoringOperatorDTO(type="merge", name="merge", depends_on=["proc_inv", "proc_rec"]),
            ],
        )
        assert dto.flow[1].type == "branching"
        assert "branches" in dto.flow[1].config
        assert dto.flow[2].depends_on == ["classify.invoices"]
        assert len(dto.flow[4].depends_on) == 2

    def test_flow_rag_pipeline_pattern(self):
        """Test complete RAG pipeline pattern from documentation."""
        dto = AuthoringFlowCreateRequest(
            flow_name="RAG Pipeline",
            flow=[
                AuthoringOperatorDTO(type="ingest_source", name="ingest", config={"paths": "./docs"}),
                AuthoringOperatorDTO(type="extract_operator", name="extract", depends_on=["ingest"]),
                AuthoringOperatorDTO(type="chunker", name="chunk", depends_on=["extract"], config={"chunk_size": 512}),
                AuthoringOperatorDTO(type="embeddings", name="embed", depends_on=["chunk"]),
                AuthoringOperatorDTO(type="vectordb", name="store", depends_on=["embed"]),
            ],
            global_config={"doc_column": "content"},
        )
        assert len(dto.flow) == 5
        assert all(len(dto.flow[i].depends_on) == 1 for i in range(1, 5))

    def test_flow_tag_deduplication(self):
        """Test tag deduplication and order preservation."""
        dto = AuthoringFlowCreateRequest(
            flow_name="test",
            flow=[AuthoringOperatorDTO(type="ingest_source", name="ingest")],
            tags=["zebra", "alpha", "beta", "alpha", "zebra"],
        )
        assert dto.tags == ["zebra", "alpha", "beta"]

    def test_flow_edge_cases(self):
        """Test edge cases: default values, max lengths, special chars."""
        # Default values when not provided
        dto = AuthoringFlowCreateRequest(
            flow_name="test",
            flow=[AuthoringOperatorDTO(type="ingest_source", name="ingest")],
        )
        assert dto.flow[0].config == {}
        assert dto.flow[0].depends_on == []
        assert dto.tags == []

        # Max valid lengths
        max_dto = AuthoringFlowCreateRequest(
            flow_name="x" * 256,
            flow=[AuthoringOperatorDTO(type="noop", name=f"op_{i}") for i in range(10000)],
        )
        assert len(max_dto.flow_name) == 256
        assert len(max_dto.flow) == 10000

        # Unicode and special chars
        unicode_dto = AuthoringFlowCreateRequest(
            flow_name="Test 测试 🚀",
            flow=[AuthoringOperatorDTO(type="ingest_source", name="ingest-docs_v2")],
        )
        assert "测试" in unicode_dto.flow_name
        assert unicode_dto.flow[0].name == "ingest-docs_v2"
