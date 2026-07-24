"""Unit tests for FlowService."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from docpipe.core.assets.flows.application.services.flow_service import FlowService
from docpipe.core.assets.flows.domain.models.flow import Flow
from docpipe.exceptions.docpipe_exceptions import (
    FlowAlreadyExistsException,
    FlowInvalidDataException,
    FlowNotFoundException,
)


class TestFlowServiceCreate:
    """Tests for FlowService.create_flow method."""

    def test_create_flow_prevents_duplicate_name(self, mock_flow_repository, sample_flow_with_id):
        """Test that create_flow prevents creating flows with duplicate names."""
        # Arrange
        existing_flow = Flow(
            flow_id="different-id",
            name=sample_flow_with_id.name,  # Same name
            definition={"doc_type": "pipeline", "pipelines": []},
        )
        mock_flow_repository.find_all.return_value = [existing_flow]
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowAlreadyExistsException, match="already exists"):
            service.create_flow(flow=sample_flow_with_id, is_elyra=True)

        # Verify save was never called
        mock_flow_repository.save.assert_not_called()

    def test_create_flow_with_valid_data(self, mock_flow_repository, sample_flow_domain):
        """Test creating a flow with valid data."""
        # Arrange
        mock_flow_repository.save.return_value = sample_flow_domain
        mock_flow_repository.find_all.return_value = []  # No existing flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.create_flow(flow=sample_flow_domain, is_elyra=True)

        # Assert
        assert result == sample_flow_domain
        mock_flow_repository.save.assert_called_once_with(sample_flow_domain)

    def test_create_flow_validates_before_saving(self, mock_flow_repository):
        """Test that flow validation occurs before saving."""
        # Arrange
        service = FlowService(repository=mock_flow_repository)
        invalid_flow = Flow(name="", definition={})  # Invalid: empty name and definition

        # Act & Assert
        with pytest.raises(FlowInvalidDataException, match="Flow name cannot be empty"):
            service.create_flow(flow=invalid_flow)

        # Verify save was never called
        mock_flow_repository.save.assert_not_called()

    def test_create_flow_with_existing_name_logs_warning(self, mock_flow_repository, sample_flow_with_id):
        """Test creating a flow when name already exists logs warning."""
        # Arrange
        existing_flow = Flow(
            flow_id="different-id",
            name=sample_flow_with_id.name,  # Same name
            definition={"doc_type": "pipeline", "pipelines": []},
        )
        mock_flow_repository.find_all.return_value = [existing_flow]
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with patch("docpipe.core.assets.flows.application.services.flow_service.logger") as mock_logger:
            with pytest.raises(FlowAlreadyExistsException, match="already exists"):
                service.create_flow(flow=sample_flow_with_id, is_elyra=True)

            # Verify warning was logged before exception
            mock_logger.warning.assert_called_once()
            assert "existing name" in mock_logger.warning.call_args[0][0].lower()

    def test_create_flow_handles_repository_exception(self, mock_flow_repository, sample_flow_domain):
        """Test that repository exceptions bubble up naturally."""
        # Arrange
        mock_flow_repository.find_all.return_value = []
        mock_flow_repository.save.side_effect = OSError("Disk full")
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(OSError, match="Disk full"):
            service.create_flow(flow=sample_flow_domain, is_elyra=True)

    def test_create_flow_with_is_elyra_false_stores_authoring_format(self, mock_flow_repository):
        """Test that is_elyra=False stores flow in authoring format without transformation."""
        # Arrange
        authoring_flow = Flow(
            flow_id="test-flow-id",
            name="Test Flow",
            definition={
                "flow_name": "Test Flow",
                "flow": [{"type": "ingest_local", "name": "node1", "config": {}, "depends_on": []}],
                "global_config": {},
                "tags": [],
            },
        )
        mock_flow_repository.find_all.return_value = []
        mock_flow_repository.save.return_value = authoring_flow
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.create_flow(flow=authoring_flow, is_elyra=False)

        # Assert - No transformation should occur, flow stored as-is
        assert result == authoring_flow
        mock_flow_repository.save.assert_called_once_with(authoring_flow)

    def test_create_flow_with_is_elyra_true_no_transformation(self, mock_flow_repository):
        """Test that is_elyra=True does not transform (flow already in Elyra format)."""
        # Arrange
        elyra_flow = Flow(
            flow_id="test-flow-id",
            name="Test Flow",
            definition={"doc_type": "pipeline", "pipelines": []},
        )
        mock_flow_repository.find_all.return_value = []
        mock_flow_repository.save.return_value = elyra_flow
        service = FlowService(repository=mock_flow_repository)

        # Act
        with patch("docpipe.utils.orchestration.elyra_converter.ElyraConverter") as mock_converter_class:
            result = service.create_flow(flow=elyra_flow, is_elyra=True)

            # Assert - converter should not be instantiated when is_elyra=True
            mock_converter_class.assert_not_called()
            assert result == elyra_flow


class TestFlowServiceGet:
    """Tests for FlowService.get_flow method."""

    def test_get_flow_validates_empty_flow_id(self, mock_flow_repository):
        """Test that get_flow validates empty flow_id."""
        # Arrange
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert - empty string
        with pytest.raises(FlowInvalidDataException, match="flow_id cannot be empty"):
            service.get_flow("")

        # Act & Assert - whitespace only
        with pytest.raises(FlowInvalidDataException, match="flow_id cannot be empty"):
            service.get_flow("   ")

        # Verify repository was never called
        mock_flow_repository.find_by_id.assert_not_called()

    def test_get_flow_with_existing_id(self, mock_flow_repository, sample_flow_with_id):
        """Test retrieving an existing flow."""
        # Arrange
        mock_flow_repository.find_by_id.return_value = sample_flow_with_id
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.get_flow("test-flow-id-123")

        # Assert
        assert result == sample_flow_with_id
        mock_flow_repository.find_by_id.assert_called_once_with("test-flow-id-123")

    def test_get_flow_with_nonexistent_id_raises_error(self, mock_flow_repository):
        """Test retrieving a non-existent flow raises FlowNotFoundException."""
        # Arrange
        mock_flow_repository.find_by_id.return_value = None
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowNotFoundException, match="Flow test-id not found"):
            service.get_flow("test-id")

    def test_get_flow_handles_repository_exception(self, mock_flow_repository):
        """Test that repository exceptions are propagated."""
        # Arrange
        mock_flow_repository.find_by_id.side_effect = OSError("Read error")
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(OSError, match="Read error"):
            service.get_flow("test-id")


class TestFlowServiceUpdate:
    """Tests for FlowService.update_flow method."""

    def test_update_flow_with_valid_data(self, mock_flow_repository, sample_flow_with_id):
        """Test updating a flow with valid data."""
        # Arrange
        mock_flow_repository.exists.return_value = True
        mock_flow_repository.update.return_value = sample_flow_with_id
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.update_flow(sample_flow_with_id)

        # Assert
        assert result == sample_flow_with_id
        mock_flow_repository.exists.assert_called_once_with("test-flow-id-123")
        mock_flow_repository.update.assert_called_once()

    def test_update_flow_updates_timestamp(self, mock_flow_repository, sample_flow_with_id):
        """Test that update_flow updates the modified_on timestamp."""
        # Arrange
        mock_flow_repository.exists.return_value = True
        mock_flow_repository.save.return_value = sample_flow_with_id
        original_modified = sample_flow_with_id.modified_on
        service = FlowService(repository=mock_flow_repository)

        # Act
        with patch("docpipe.core.assets.flows.domain.models.flow.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)
            service.update_flow(sample_flow_with_id)

        # Assert
        assert sample_flow_with_id.modified_on != original_modified

    def test_update_flow_without_id_raises_error(self, mock_flow_repository, sample_flow_domain):
        """Test updating a flow without flow_id raises FlowInvalidDataException."""
        # Arrange
        sample_flow_domain.flow_id = None
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowInvalidDataException, match="Flow ID is required for update"):
            service.update_flow(sample_flow_domain)

    def test_update_flow_with_nonexistent_id_raises_error(self, mock_flow_repository, sample_flow_with_id):
        """Test updating a non-existent flow raises FlowNotFoundException."""
        # Arrange
        mock_flow_repository.exists.return_value = False
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowNotFoundException, match="not found"):
            service.update_flow(sample_flow_with_id)

    def test_update_flow_validates_before_saving(self, mock_flow_repository, sample_flow_with_id):
        """Test that flow validation occurs before updating."""
        # Arrange
        mock_flow_repository.exists.return_value = True
        service = FlowService(repository=mock_flow_repository)
        sample_flow_with_id.name = ""  # Make it invalid

        # Act & Assert
        with pytest.raises(FlowInvalidDataException, match="Flow name cannot be empty"):
            service.update_flow(sample_flow_with_id)

        # Verify save was never called
        mock_flow_repository.save.assert_not_called()


class TestFlowServicePartialUpdate:
    """Tests for FlowService.partial_update_flow method."""

    def test_partial_update_flow_validates_empty_updates(self, mock_flow_repository):
        """Test that partial_update_flow validates empty updates dictionary."""
        # Arrange
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowInvalidDataException, match="updates dictionary cannot be empty"):
            service.partial_update_flow("test-123", {})

        # Verify repository was never called
        mock_flow_repository.find_by_id.assert_not_called()

    def test_partial_update_flow_tracks_updated_fields(self, mock_flow_repository, sample_flow_with_id, caplog):
        """Test that partial_update_flow tracks and logs updated fields."""
        import logging

        caplog.set_level(logging.INFO)

        # Arrange
        mock_flow_repository.find_by_id.return_value = sample_flow_with_id
        mock_flow_repository.update.return_value = sample_flow_with_id
        service = FlowService(repository=mock_flow_repository)
        updates = {"name": "new_name", "description": "new_desc"}

        # Act
        result = service.partial_update_flow("test-flow-id-123", updates)

        # Assert
        assert result.name == "new_name"
        assert result.description == "new_desc"
        assert "Updated fields" in caplog.text
        assert "name" in caplog.text
        assert "description" in caplog.text

    def test_partial_update_flow_with_name_change(self, mock_flow_repository, sample_flow_with_id):
        """Test partial update with name change."""
        # Arrange
        mock_flow_repository.find_by_id.return_value = sample_flow_with_id
        mock_flow_repository.update.return_value = sample_flow_with_id
        service = FlowService(repository=mock_flow_repository)
        updates = {"name": "Updated Flow Name"}

        # Act
        result = service.partial_update_flow("test-flow-id-123", updates)

        # Assert
        assert result.name == "Updated Flow Name"
        mock_flow_repository.update.assert_called_once()

    def test_partial_update_flow_without_name_change(self, mock_flow_repository, sample_flow_with_id):
        """Test partial update without name change."""
        # Arrange
        mock_flow_repository.find_by_id.return_value = sample_flow_with_id
        mock_flow_repository.update.return_value = sample_flow_with_id
        service = FlowService(repository=mock_flow_repository)
        updates = {"description": "Updated description"}

        # Act
        result = service.partial_update_flow("test-flow-id-123", updates)

        # Assert
        assert result.description == "Updated description"
        mock_flow_repository.update.assert_called_once()

    def test_partial_update_flow_ignores_protected_fields(self, mock_flow_repository, sample_flow_with_id, caplog):
        """Test that protected fields (flow_id, created_on, created_by) are not updated."""
        import logging

        caplog.set_level(logging.WARNING)

        # Arrange
        mock_flow_repository.find_by_id.return_value = sample_flow_with_id
        mock_flow_repository.update.return_value = sample_flow_with_id
        service = FlowService(repository=mock_flow_repository)
        original_id = sample_flow_with_id.flow_id
        original_created = sample_flow_with_id.created_on
        updates = {
            "flow_id": "new-id",
            "created_on": datetime(2025, 1, 1, tzinfo=UTC),
            "created_by": "hacker",
        }

        # Act
        result = service.partial_update_flow("test-flow-id-123", updates)

        # Assert
        assert result.flow_id == original_id
        assert result.created_on == original_created
        # Verify warnings were logged for protected fields
        assert "protected field" in caplog.text.lower()

    def test_partial_update_flow_validates_before_saving(self, mock_flow_repository, sample_flow_with_id):
        """Test that validation occurs before file operations."""
        # Arrange
        mock_flow_repository.find_by_id.return_value = sample_flow_with_id
        service = FlowService(repository=mock_flow_repository)
        updates = {"name": ""}  # Invalid empty name

        # Act & Assert
        with pytest.raises(FlowInvalidDataException, match="Flow name cannot be empty"):
            service.partial_update_flow("test-flow-id-123", updates)

        # Verify update was never called
        mock_flow_repository.update.assert_not_called()

    def test_partial_update_flow_with_nonexistent_id_raises_error(self, mock_flow_repository):
        """Test partial update with non-existent flow ID raises FlowNotFoundException."""
        # Arrange
        mock_flow_repository.find_by_id.return_value = None
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowNotFoundException):
            service.partial_update_flow("nonexistent-id", {"name": "New Name"})


class TestFlowServiceDelete:
    """Tests for FlowService.delete_flow method."""

    def test_delete_flow_validates_empty_flow_id(self, mock_flow_repository):
        """Test that delete_flow validates empty flow_id."""
        # Arrange
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert - empty string
        with pytest.raises(FlowInvalidDataException, match="flow_id cannot be empty"):
            service.delete_flow("")

        # Act & Assert - whitespace only
        with pytest.raises(FlowInvalidDataException, match="flow_id cannot be empty"):
            service.delete_flow("   ")

        # Verify repository was never called
        mock_flow_repository.delete.assert_not_called()

    def test_delete_flow_with_existing_id(self, mock_flow_repository):
        """Test deleting an existing flow."""
        # Arrange
        mock_flow_repository.delete.return_value = True
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.delete_flow("test-flow-id")

        # Assert
        assert result is True
        mock_flow_repository.delete.assert_called_once_with("test-flow-id")

    def test_delete_flow_with_nonexistent_id(self, mock_flow_repository):
        """Test deleting a non-existent flow raises FlowNotFoundException."""
        # Arrange
        mock_flow_repository.delete.return_value = False
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowNotFoundException, match="Flow nonexistent-id not found"):
            service.delete_flow("nonexistent-id")

    def test_delete_flow_handles_repository_exception(self, mock_flow_repository):
        """Test that repository exceptions are propagated."""
        # Arrange
        mock_flow_repository.delete.side_effect = OSError("Delete error")
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(OSError, match="Delete error"):
            service.delete_flow("test-id")


class TestFlowServiceBulkDelete:
    """Tests for FlowService.bulk_delete_flows method."""

    def test_bulk_delete_flows_success(self, mock_flow_repository):
        """Test bulk delete with all flows deleted successfully."""
        # Arrange
        flow_ids = ["flow-1", "flow-2", "flow-3"]
        mock_flow_repository.bulk_delete.return_value = {
            "deleted": flow_ids,
            "failed": [],
            "total_requested": 3,
            "total_deleted": 3,
            "total_failed": 0,
        }
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.bulk_delete_flows(flow_ids)

        # Assert
        assert result["total_deleted"] == 3
        assert result["total_failed"] == 0
        assert result["deleted"] == flow_ids
        assert result["failed"] == []
        mock_flow_repository.bulk_delete.assert_called_once_with(flow_ids)

    def test_bulk_delete_flows_partial_failure(self, mock_flow_repository):
        """Test bulk delete with some flows succeeding and some failing."""
        # Arrange
        flow_ids = ["flow-1", "flow-2", "flow-3"]
        mock_flow_repository.bulk_delete.return_value = {
            "deleted": ["flow-1", "flow-3"],
            "failed": [{"flow_id": "flow-2", "error": "Flow flow-2 not found"}],
            "total_requested": 3,
            "total_deleted": 2,
            "total_failed": 1,
        }
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.bulk_delete_flows(flow_ids)

        # Assert
        assert result["total_deleted"] == 2
        assert result["total_failed"] == 1
        assert len(result["deleted"]) == 2
        assert len(result["failed"]) == 1
        assert result["failed"][0]["flow_id"] == "flow-2"
        mock_flow_repository.bulk_delete.assert_called_once_with(flow_ids)

    def test_bulk_delete_flows_empty_list(self, mock_flow_repository):
        """Test bulk delete with empty flow_ids list raises FlowInvalidDataException."""
        # Arrange
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowInvalidDataException, match="flow_ids list cannot be empty"):
            service.bulk_delete_flows([])

        # Verify repository was never called
        mock_flow_repository.bulk_delete.assert_not_called()

    def test_bulk_delete_flows_all_fail(self, mock_flow_repository):
        """Test bulk delete where all deletions fail."""
        # Arrange
        flow_ids = ["nonexistent-1", "nonexistent-2"]
        mock_flow_repository.bulk_delete.return_value = {
            "deleted": [],
            "failed": [
                {"flow_id": "nonexistent-1", "error": "Flow nonexistent-1 not found"},
                {"flow_id": "nonexistent-2", "error": "Flow nonexistent-2 not found"},
            ],
            "total_requested": 2,
            "total_deleted": 0,
            "total_failed": 2,
        }
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.bulk_delete_flows(flow_ids)

        # Assert
        assert result["total_deleted"] == 0
        assert result["total_failed"] == 2
        assert result["deleted"] == []
        assert len(result["failed"]) == 2
        mock_flow_repository.bulk_delete.assert_called_once_with(flow_ids)

    def test_bulk_delete_flows_handles_repository_exception(self, mock_flow_repository):
        """Test that repository exceptions are propagated."""
        # Arrange
        flow_ids = ["flow-1", "flow-2"]
        mock_flow_repository.bulk_delete.side_effect = OSError("Disk error")
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(OSError, match="Disk error"):
            service.bulk_delete_flows(flow_ids)

    def test_bulk_delete_flows_parallel_execution(self, mock_flow_repository):
        """Test that bulk delete can handle parallel execution."""
        flow_ids = [f"flow-{i}" for i in range(20)]

        # Mock repository to return success for all
        mock_flow_repository.bulk_delete.return_value = {
            "deleted": flow_ids,
            "failed": [],
            "total_requested": 20,
            "total_deleted": 20,
            "total_failed": 0,
        }

        service = FlowService(repository=mock_flow_repository)
        result = service.bulk_delete_flows(flow_ids)

        assert result["total_deleted"] == 20
        assert len(result["deleted"]) == 20
        assert result["total_failed"] == 0
        # Verify bulk_delete was called once with the flow_ids
        mock_flow_repository.bulk_delete.assert_called_once_with(flow_ids)

    def test_bulk_delete_flows_with_thread_failures(self, mock_flow_repository):
        """Test that bulk delete handles thread failures gracefully."""
        flow_ids = [f"flow-{i}" for i in range(10)]

        # Mock repository to simulate some deletions failing
        mock_flow_repository.bulk_delete.return_value = {
            "deleted": ["flow-0", "flow-2", "flow-4", "flow-6", "flow-8"],
            "failed": [
                {"flow_id": "flow-1", "error": "Permission denied"},
                {"flow_id": "flow-3", "error": "File not found"},
                {"flow_id": "flow-5", "error": "Lock timeout"},
                {"flow_id": "flow-7", "error": "I/O error"},
                {"flow_id": "flow-9", "error": "Disk full"},
            ],
            "total_requested": 10,
            "total_deleted": 5,
            "total_failed": 5,
        }

        service = FlowService(repository=mock_flow_repository)
        result = service.bulk_delete_flows(flow_ids)

        # Verify partial success
        assert result["total_requested"] == 10
        assert result["total_deleted"] == 5
        assert result["total_failed"] == 5
        assert len(result["deleted"]) == 5
        assert len(result["failed"]) == 5

        # Verify failed flows have error messages
        for failed_item in result["failed"]:
            assert "flow_id" in failed_item
            assert "error" in failed_item
            assert failed_item["error"]  # Error message is not empty

        # Verify repository was called correctly
        mock_flow_repository.bulk_delete.assert_called_once_with(flow_ids)


class TestFlowServiceList:
    """Tests for FlowService.list_flows method."""

    def test_list_flows_validates_pagination_skip_negative(self, mock_flow_repository):
        """Test that list_flows validates skip parameter."""
        # Arrange
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowInvalidDataException, match="skip must be >= 0"):
            service.list_flows(skip=-1)

    def test_list_flows_validates_pagination_limit_zero(self, mock_flow_repository):
        """Test that list_flows validates limit parameter (zero)."""
        # Arrange
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowInvalidDataException, match="limit must be > 0"):
            service.list_flows(limit=0)

    def test_list_flows_validates_pagination_limit_negative(self, mock_flow_repository):
        """Test that list_flows validates limit parameter (negative)."""
        # Arrange
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert
        with pytest.raises(FlowInvalidDataException, match="limit must be > 0"):
            service.list_flows(limit=-5)

    def test_list_flows_without_filters(self, mock_flow_repository, multiple_sample_flows):
        """Test listing all flows without filters."""
        # Arrange
        mock_flow_repository.find_all.return_value = multiple_sample_flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.list_flows()

        # Assert
        assert len(result) == 5
        assert result == multiple_sample_flows

    def test_list_flows_with_pagination(self, mock_flow_repository, multiple_sample_flows):
        """Test listing flows with pagination."""
        # Arrange
        mock_flow_repository.find_all.return_value = multiple_sample_flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.list_flows(skip=2, limit=2)

        # Assert
        assert len(result) == 2
        assert result[0].name == "Test Flow 2"
        assert result[1].name == "Test Flow 3"

    def test_list_flows_with_name_filter(self, mock_flow_repository, multiple_sample_flows):
        """Test listing flows with name filter."""
        # Arrange
        mock_flow_repository.find_all.return_value = multiple_sample_flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.list_flows(name_filter="Flow 2")

        # Assert
        assert len(result) == 1
        assert result[0].name == "Test Flow 2"

    def test_list_flows_with_tags_filter(self, mock_flow_repository, multiple_sample_flows):
        """Test listing flows with tags filter."""
        # Arrange
        mock_flow_repository.find_all.return_value = multiple_sample_flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.list_flows(tags_filter=["tag-1"])

        # Assert
        assert len(result) == 1
        assert "tag-1" in result[0].tags

    def test_list_flows_with_is_hidden_filter(self, mock_flow_repository, multiple_sample_flows):
        """Test listing flows with is_hidden filter."""
        # Arrange
        mock_flow_repository.find_all.return_value = multiple_sample_flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.list_flows(is_hidden=True)

        # Assert
        assert len(result) == 3  # Flows 0, 2, 4 are hidden
        assert all(flow.is_hidden for flow in result)

    def test_list_flows_with_combined_filters(self, mock_flow_repository, multiple_sample_flows):
        """Test listing flows with multiple filters combined."""
        # Arrange
        mock_flow_repository.find_all.return_value = multiple_sample_flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.list_flows(name_filter="Flow", is_hidden=False, skip=0, limit=10)

        # Assert
        assert len(result) == 2  # Flows 1 and 3 are not hidden
        assert all(not flow.is_hidden for flow in result)


class TestFlowServiceCount:
    """Tests for FlowService.count_flows method."""

    def test_count_flows_without_filters(self, mock_flow_repository, multiple_sample_flows):
        """Test counting all flows without filters."""
        # Arrange
        mock_flow_repository.find_all.return_value = multiple_sample_flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.count_flows()

        # Assert
        assert result == 5

    def test_count_flows_with_name_filter(self, mock_flow_repository, multiple_sample_flows):
        """Test counting flows with name filter."""
        # Arrange
        mock_flow_repository.find_all.return_value = multiple_sample_flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.count_flows(name_filter="Flow 2")

        # Assert
        assert result == 1

    def test_count_flows_with_is_hidden_filter(self, mock_flow_repository, multiple_sample_flows):
        """Test counting flows with is_hidden filter."""
        # Arrange
        mock_flow_repository.find_all.return_value = multiple_sample_flows
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.count_flows(is_hidden=True)

        # Assert
        assert result == 3


class TestFlowServiceExists:
    """Tests for FlowService.flow_exists method."""

    def test_flow_exists_validates_empty_flow_id(self, mock_flow_repository):
        """Test that flow_exists validates empty flow_id."""
        # Arrange
        service = FlowService(repository=mock_flow_repository)

        # Act & Assert - empty string
        with pytest.raises(FlowInvalidDataException, match="flow_id cannot be empty"):
            service.flow_exists("")

        # Act & Assert - whitespace only
        with pytest.raises(FlowInvalidDataException, match="flow_id cannot be empty"):
            service.flow_exists("   ")

        # Verify repository was never called
        mock_flow_repository.find_by_id.assert_not_called()

    def test_flow_exists_returns_true_for_existing_flow(self, mock_flow_repository):
        """Test flow_exists returns True for existing flow."""
        # Arrange
        mock_flow_repository.exists.return_value = True
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.flow_exists("test-id")

        # Assert
        assert result is True
        mock_flow_repository.exists.assert_called_once_with("test-id")

    def test_flow_exists_returns_false_for_nonexistent_flow(self, mock_flow_repository):
        """Test flow_exists returns False for non-existent flow."""
        # Arrange
        mock_flow_repository.exists.return_value = False
        service = FlowService(repository=mock_flow_repository)

        # Act
        result = service.flow_exists("nonexistent-id")

        # Assert
        assert result is False
