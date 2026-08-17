"""Unit tests for Flow domain model validation."""

from datetime import UTC, datetime

import pytest

from docpipe.core.assets.flows.domain.models.flow import Flow
from docpipe.exceptions.docpipe_exceptions import AssetInvalidDataException


class TestFlowCreation:
    """Tests for Flow object creation and initialization."""

    def test_create_flow_with_minimal_required_fields(self):
        """Test creating a flow with only required fields."""
        # Arrange & Act
        flow = Flow(name="Test Flow", definition={"doc_type": "pipeline", "pipelines": []})

        # Assert
        assert flow.name == "Test Flow"
        assert flow.definition == {"doc_type": "pipeline", "pipelines": []}
        assert flow.flow_id is not None  # Auto-generated
        assert flow.created_on is not None  # Auto-generated
        assert flow.modified_on is not None  # Auto-generated
        assert flow.tags == []  # Default value
        assert flow.is_hidden is False  # Default value
        assert flow.flow_version == "2.0"  # Default value

    def test_create_flow_with_all_fields(self, sample_flow_data):
        """Test creating a flow with all fields specified."""
        # Arrange & Act
        flow = Flow(
            asset_id="custom-id",
            name=sample_flow_data["name"],
            description=sample_flow_data["description"],
            definition=sample_flow_data["definition"],
            tags=sample_flow_data["tags"],
            container_kind=sample_flow_data["container_kind"],
            container_id=sample_flow_data["container_id"],
            is_hidden=sample_flow_data["is_hidden"],
            flow_version=sample_flow_data["flow_version"],
            job_id=sample_flow_data["job_id"],
            created_by=sample_flow_data["created_by"],
            created_on=datetime(2024, 1, 1, tzinfo=UTC),
            modified_on=datetime(2024, 1, 1, tzinfo=UTC),
        )

        # Assert
        assert flow.flow_id == "custom-id"  # flow_id is alias for asset_id
        assert flow.name == sample_flow_data["name"]
        assert flow.description == sample_flow_data["description"]
        assert flow.tags == sample_flow_data["tags"]
        assert flow.container_kind == sample_flow_data["container_kind"]

    def test_create_flow_auto_generates_flow_id(self):
        """Test that flow_id is auto-generated if not provided."""
        # Arrange & Act
        flow = Flow(name="Test", definition={})

        # Assert
        assert flow.flow_id is not None
        assert isinstance(flow.flow_id, str)
        assert len(flow.flow_id) > 0

    def test_create_flow_auto_generates_timestamps(self):
        """Test that timestamps are auto-generated if not provided."""
        # Arrange & Act
        flow = Flow(name="Test", definition={})

        # Assert
        assert flow.created_on is not None
        assert flow.modified_on is not None
        assert isinstance(flow.created_on, datetime)
        assert isinstance(flow.modified_on, datetime)

    def test_create_flow_initializes_empty_tags_list(self):
        """Test that tags list is initialized as empty if not provided."""
        # Arrange & Act
        flow = Flow(name="Test", definition={})

        # Assert
        assert flow.tags == []
        assert isinstance(flow.tags, list)


class TestFlowNameValidation:
    """Tests for Flow name validation."""

    def test_validate_flow_with_valid_name(self):
        """Test validation passes with valid name."""
        # Arrange
        flow = Flow(name="Valid Flow Name", definition={"nodes": []})

        # Act & Assert
        flow.validate()  # Should not raise

    def test_validate_flow_with_empty_name_raises_error(self):
        """Test validation fails with empty name."""
        # Arrange
        flow = Flow(name="", definition={"nodes": []})

        # Act & Assert
        with pytest.raises(AssetInvalidDataException, match="flow name cannot be empty"):
            flow.validate()

    def test_validate_flow_with_whitespace_only_name_raises_error(self):
        """Test validation fails with whitespace-only name."""
        # Arrange
        flow = Flow(name="   ", definition={"nodes": []})

        # Act & Assert
        with pytest.raises(AssetInvalidDataException, match="flow name cannot be empty"):
            flow.validate()

    def test_validate_flow_with_name_exceeding_255_chars_raises_error(self):
        """Test validation fails with name exceeding 255 characters."""
        # Arrange
        long_name = "x" * 256
        flow = Flow(name=long_name, definition={"nodes": []})

        # Act & Assert
        with pytest.raises(AssetInvalidDataException, match="flow name cannot exceed 255 characters"):
            flow.validate()

    def test_validate_flow_with_name_exactly_255_chars_passes(self):
        """Test validation passes with name exactly 255 characters."""
        # Arrange
        name_255 = "x" * 255
        flow = Flow(name=name_255, definition={"nodes": []})

        # Act & Assert
        flow.validate()  # Should not raise

    def test_validate_flow_with_special_characters_in_name_passes(self):
        """Test validation passes with special characters in name."""
        # Arrange
        flow = Flow(name="Flow-Name_123 (Test)", definition={"nodes": []})

        # Act & Assert
        flow.validate()  # Should not raise


class TestFlowDescriptionValidation:
    """Tests for Flow description validation."""

    def test_validate_flow_with_valid_description(self):
        """Test validation passes with valid description."""
        # Arrange
        flow = Flow(
            name="Test",
            description="This is a valid description",
            definition={"nodes": []},
        )

        # Act & Assert
        flow.validate()  # Should not raise

    def test_validate_flow_with_none_description_passes(self):
        """Test validation passes with None description."""
        # Arrange
        flow = Flow(name="Test", description=None, definition={"nodes": []})

        # Act & Assert
        flow.validate()  # Should not raise

    def test_validate_flow_with_empty_description_passes(self):
        """Test validation passes with empty description."""
        # Arrange
        flow = Flow(name="Test", description="", definition={"nodes": []})

        # Act & Assert
        flow.validate()  # Should not raise

    def test_validate_flow_with_description_exceeding_2000_chars_raises_error(self):
        """Test validation fails with description exceeding 2000 characters."""
        # Arrange
        long_description = "x" * 2001
        flow = Flow(name="Test", description=long_description, definition={"nodes": []})

        # Act & Assert
        with pytest.raises(
            AssetInvalidDataException,
            match="flow description cannot exceed 2000 characters",
        ):
            flow.validate()

    def test_validate_flow_with_description_exactly_2000_chars_passes(self):
        """Test validation passes with description exactly 2000 characters."""
        # Arrange
        description_2000 = "x" * 2000
        flow = Flow(name="Test", description=description_2000, definition={"nodes": []})

        # Act & Assert
        flow.validate()  # Should not raise


class TestFlowDefinitionValidation:
    """Tests for Flow definition validation."""

    def test_validate_flow_with_valid_definition(self):
        """Test validation passes with valid definition."""
        # Arrange
        flow = Flow(name="Test", definition={"doc_type": "pipeline", "pipelines": []})

        # Act & Assert
        flow.validate()  # Should not raise

    def test_validate_flow_with_empty_definition_raises_error(self):
        """Test validation fails with empty definition."""
        # Arrange
        flow = Flow(name="Test", definition={})

        # Act & Assert
        from docpipe.exceptions.docpipe_exceptions import AssetInvalidDataException

        with pytest.raises(AssetInvalidDataException, match="Flow definition cannot be empty"):
            flow.validate()

    def test_validate_flow_with_non_dict_definition_raises_error(self):
        """Test validation fails with non-dictionary definition."""
        # Arrange
        flow = Flow(name="Test", definition="not a dict")  # type: ignore

        # Act & Assert
        from docpipe.exceptions.docpipe_exceptions import AssetInvalidDataException

        with pytest.raises(AssetInvalidDataException, match="Flow definition must be a dictionary"):
            flow.validate()

    def test_validate_flow_with_complex_definition_passes(self, sample_flow_data):
        """Test validation passes with complex Elyra pipeline definition."""
        # Arrange
        flow = Flow(name="Test", definition=sample_flow_data["definition"])

        # Act & Assert
        flow.validate()  # Should not raise

    def test_validate_flow_with_docpipe_definition_passes(self):
        """Test validation passes with docling-pipelines format definition."""
        # Arrange
        definition = {
            "nodes": [{"id": "node1", "operator_type": "IngestSourceOperator"}],
        }
        flow = Flow(name="Test", definition=definition)

        # Act & Assert
        flow.validate()  # Should not raise


class TestFlowUpdateTimestamp:
    """Tests for Flow.update_timestamp method."""

    def test_update_timestamp_changes_modified_on(self):
        """Test that update_timestamp changes modified_on."""
        # Arrange
        flow = Flow(
            name="Test",
            definition={"nodes": []},
            created_on=datetime(2024, 1, 1, tzinfo=UTC),
            modified_on=datetime(2024, 1, 1, tzinfo=UTC),
        )
        original_modified = flow.modified_on

        # Act
        flow.update_timestamp()

        # Assert
        assert flow.modified_on != original_modified
        assert flow.modified_on is not None and original_modified is not None
        assert flow.modified_on > original_modified

    def test_update_timestamp_does_not_change_created_on(self):
        """Test that update_timestamp does not change created_on."""
        # Arrange
        created_time = datetime(2024, 1, 1, tzinfo=UTC)
        flow = Flow(
            name="Test",
            definition={"nodes": []},
            created_on=created_time,
            modified_on=created_time,
        )

        # Act
        flow.update_timestamp()

        # Assert
        assert flow.created_on == created_time


class TestFlowToDictConversion:
    """Tests for Flow.to_dict method."""

    def test_to_dict_returns_all_fields(self, sample_flow_with_id):
        """Test that to_dict returns all flow fields."""
        # Act
        result = sample_flow_with_id.to_dict()

        # Assert
        assert "flow_id" in result
        assert "name" in result
        assert "description" in result
        assert "definition" in result
        assert "tags" in result
        assert "container_kind" in result
        assert "container_id" in result
        assert "is_hidden" in result
        assert "flow_version" in result
        assert "created_on" in result
        assert "modified_on" in result
        assert "job_id" in result
        assert "created_by" in result
        assert "modified_by" in result
        assert "href" in result

    def test_to_dict_converts_datetime_to_isoformat(self, sample_flow_with_id):
        """Test that to_dict converts datetime objects to ISO format strings."""
        # Act
        result = sample_flow_with_id.to_dict()

        # Assert
        assert isinstance(result["created_on"], str)
        assert isinstance(result["modified_on"], str)
        assert "T" in result["created_on"]  # ISO format contains 'T'

    def test_to_dict_preserves_definition_structure(self, sample_flow_with_id):
        """Test that to_dict preserves definition dictionary structure."""
        # Act
        result = sample_flow_with_id.to_dict()

        # Assert
        assert isinstance(result["definition"], dict)
        assert result["definition"] == sample_flow_with_id.definition

    def test_to_dict_handles_none_values(self):
        """Test that to_dict handles None values correctly."""
        # Arrange
        flow = Flow(
            name="Test",
            definition={"nodes": []},
            description=None,
            container_kind=None,
            job_id=None,
        )

        # Act
        result = flow.to_dict()

        # Assert
        assert result["description"] is None
        assert result["container_kind"] is None
        assert result["job_id"] is None


class TestFlowFromDictConversion:
    """Tests for Flow.from_dict method."""

    def test_from_dict_creates_flow_from_complete_data(self, sample_flow_data):
        """Test that from_dict creates a Flow from complete data."""
        # Arrange
        data = {
            **sample_flow_data,
            "flow_id": "test-id",
            "created_on": "2024-01-01T12:00:00+00:00",
            "modified_on": "2024-01-01T12:00:00+00:00",
        }

        # Act
        flow = Flow.from_dict(data=data)

        # Assert
        assert flow.flow_id == "test-id"
        assert flow.name == sample_flow_data["name"]
        assert flow.description == sample_flow_data["description"]
        assert isinstance(flow.created_on, datetime)
        assert isinstance(flow.modified_on, datetime)

    def test_from_dict_parses_datetime_strings(self):
        """Test that from_dict parses datetime strings correctly."""
        # Arrange
        data = {
            "name": "Test",
            "definition": {"nodes": []},
            "created_on": "2024-01-01T12:00:00Z",
            "modified_on": "2024-01-02T13:30:00+00:00",
        }

        # Act
        flow = Flow.from_dict(data=data)

        # Assert
        assert isinstance(flow.created_on, datetime)
        assert isinstance(flow.modified_on, datetime)
        assert flow.created_on.year == 2024
        assert flow.created_on.month == 1
        assert flow.created_on.day == 1

    def test_from_dict_handles_missing_optional_fields(self):
        """Test that from_dict handles missing optional fields."""
        # Arrange
        data = {"name": "Test", "definition": {"nodes": []}}

        # Act
        flow = Flow.from_dict(data=data)

        # Assert
        assert flow.name == "Test"
        assert flow.description is None
        assert flow.container_kind is None
        assert flow.tags == []

    def test_from_dict_preserves_tags_list(self):
        """Test that from_dict preserves tags list."""
        # Arrange
        data = {
            "name": "Test",
            "definition": {"nodes": []},
            "tags": ["tag1", "tag2", "tag3"],
        }

        # Act
        flow = Flow.from_dict(data=data)

        # Assert
        assert flow.tags == ["tag1", "tag2", "tag3"]

    def test_from_dict_sets_default_values(self):
        """Test that from_dict sets default values for missing fields."""
        # Arrange
        data = {"name": "Test", "definition": {"nodes": []}}

        # Act
        flow = Flow.from_dict(data=data)

        # Assert
        assert flow.is_hidden is False
        assert flow.flow_version == "2.0"
        assert flow.tags == []


class TestFlowRoundTripConversion:
    """Tests for round-trip conversion (to_dict -> from_dict)."""

    def test_roundtrip_conversion_preserves_data(self, sample_flow_with_id):
        """Test that converting to dict and back preserves all data."""
        # Act
        dict_data = sample_flow_with_id.to_dict()
        restored_flow = Flow.from_dict(data=dict_data)

        # Assert
        assert restored_flow.flow_id == sample_flow_with_id.flow_id
        assert restored_flow.name == sample_flow_with_id.name
        assert restored_flow.description == sample_flow_with_id.description
        assert restored_flow.definition == sample_flow_with_id.definition
        assert restored_flow.tags == sample_flow_with_id.tags
        assert restored_flow.container_kind == sample_flow_with_id.container_kind
        assert restored_flow.is_hidden == sample_flow_with_id.is_hidden

    def test_roundtrip_conversion_preserves_timestamps(self, sample_flow_with_id):
        """Test that round-trip conversion preserves timestamp precision."""
        # Act
        dict_data = sample_flow_with_id.to_dict()
        restored_flow = Flow.from_dict(data=dict_data)

        # Assert - Compare timestamps (allowing for microsecond precision loss in ISO format)
        assert restored_flow.created_on is not None and sample_flow_with_id.created_on is not None
        assert restored_flow.modified_on is not None and sample_flow_with_id.modified_on is not None
        assert restored_flow.created_on.replace(microsecond=0) == sample_flow_with_id.created_on.replace(microsecond=0)
        assert restored_flow.modified_on.replace(microsecond=0) == sample_flow_with_id.modified_on.replace(
            microsecond=0
        )
