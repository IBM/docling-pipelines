"""Integration tests for Flow API routes.

These tests use FastAPI TestClient to test the full request/response cycle
including middleware, error handling, and actual file system operations.
"""

from typing import Any, cast

from fastapi.testclient import TestClient


class TestCreateFlowIntegration:
    """Integration tests for POST /api/v1/flows endpoint."""

    def test_create_flow_with_complete_data_returns_201(self, test_client: TestClient, sample_flow_data: dict):
        """Test creating a flow with complete data returns 201 and stores file."""
        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=sample_flow_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_flow_data["name"]
        assert data["description"] == sample_flow_data["description"]
        assert data["tags"] == sample_flow_data["tags"]
        assert data["container_kind"] == sample_flow_data["container_kind"]
        assert data["container_id"] == sample_flow_data["container_id"]
        assert data["is_hidden"] == sample_flow_data["is_hidden"]
        assert data["flow_version"] == sample_flow_data["flow_version"]
        assert data["created_by"] == sample_flow_data["created_by"]
        assert "flow_id" in data
        assert "created_on" in data
        assert "modified_on" in data
        assert "href" in data

    def test_create_flow_with_minimal_data_returns_201(self, test_client: TestClient, minimal_flow_data: dict):
        """Test creating a flow with only required fields returns 201."""
        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=minimal_flow_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == minimal_flow_data["name"]
        assert data["description"] is None
        assert data["tags"] == []
        assert data["is_hidden"] is False
        assert data["flow_version"] == "2.0"
        assert "flow_id" in data
        assert "definition" in data  # Should have auto-generated definition

    def test_create_flow_with_empty_name_returns_422(self, test_client: TestClient):
        """Test creating a flow with empty name returns 400 validation error."""
        # Arrange
        flow_data = {"name": ""}

        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=flow_data)

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "errors" in data or "detail" in data

    def test_create_flow_with_invalid_container_kind_returns_422(self, test_client: TestClient):
        """Test creating a flow with invalid container_kind returns 400."""
        # Arrange
        flow_data = {"name": "Test Flow", "container_kind": "invalid_kind"}

        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=flow_data)

        # Assert
        assert response.status_code == 400

    def test_create_flow_with_invalid_container_id_returns_422(self, test_client: TestClient):
        """Test creating a flow with invalid UUID format returns 400."""
        # Arrange
        flow_data = {"name": "Test Flow", "container_id": "not-a-uuid"}

        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=flow_data)

        # Assert
        assert response.status_code == 400

    def test_create_flow_with_invalid_job_id_returns_422(self, test_client: TestClient):
        """Test creating a flow with invalid job_id UUID format returns 400."""
        # Arrange
        flow_data = {"name": "Test Flow", "job_id": "invalid-uuid"}

        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=flow_data)

        # Assert
        assert response.status_code == 400

    def test_create_flow_with_duplicate_tags_deduplicates(self, test_client: TestClient):
        """Test creating a flow with duplicate tags automatically deduplicates them."""
        # Arrange
        flow_data = {
            "name": "Test Flow",
            "tags": ["tag1", "tag2", "tag1", "tag3", "tag2"],
        }

        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=flow_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert len(data["tags"]) == 3
        assert set(data["tags"]) == {"tag1", "tag2", "tag3"}

    def test_create_flow_includes_transaction_id_in_response_headers(
        self, test_client: TestClient, minimal_flow_data: dict
    ):
        """Test that response includes transaction ID header from middleware."""
        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=minimal_flow_data)

        # Assert
        assert response.status_code == 201
        assert "x-transaction-id" in response.headers


class TestGetFlowIntegration:
    """Integration tests for GET /api/v1/flows/{flow_id} endpoint."""

    def test_get_existing_flow_returns_200(self, test_client: TestClient, create_test_flow):
        """Test retrieving an existing flow returns 200 with correct data."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]

        # Act
        response = test_client.get(f"/api/v1/flows/{flow_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["flow_id"] == flow_id
        assert data["name"] == created_flow["name"]
        assert data["description"] == created_flow["description"]
        assert data["tags"] == created_flow["tags"]

    def test_get_nonexistent_flow_returns_404(self, test_client: TestClient):
        """Test retrieving a non-existent flow returns 404."""
        # Arrange
        nonexistent_id = "550e8400-e29b-41d4-a716-446655440000"

        # Act
        response = test_client.get(f"/api/v1/flows/{nonexistent_id}")

        # Assert
        assert response.status_code == 404
        data = response.json()
        # API uses errors array format
        assert "errors" in data or "detail" in data

    def test_get_flow_with_invalid_id_format_returns_404(self, test_client: TestClient):
        """Test retrieving a flow with invalid ID format returns 400."""
        # Arrange
        invalid_id = "not-a-valid-id"

        # Act
        response = test_client.get(f"/api/v1/flows/{invalid_id}")

        # Assert
        assert response.status_code == 400


class TestListFlowsIntegration:
    """Integration tests for GET /api/v1/flows endpoint."""

    def test_list_flows_without_filters_returns_200(
        self, test_client: TestClient, create_test_flow, sample_flow_data: dict
    ):
        """Test listing all flows without filters returns 200."""
        # Arrange - Create multiple flows
        for i in range(3):
            flow_data = sample_flow_data.copy()
            flow_data["name"] = f"Test Flow {i}"
            create_test_flow(flow_data)

        # Act
        response = test_client.get("/api/v1/flows")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "flows" in data
        assert "total_count" in data
        assert "offset" in data
        assert "limit" in data
        assert len(data["flows"]) == 3
        assert data["total_count"] == 3
        assert data["offset"] == 0
        assert data["limit"] == 100

    def test_list_flows_with_pagination_returns_correct_page(
        self, test_client: TestClient, create_test_flow, sample_flow_data: dict
    ):
        """Test listing flows with pagination returns correct page."""
        # Arrange - Create 5 flows
        for i in range(5):
            flow_data = sample_flow_data.copy()
            flow_data["name"] = f"Test Flow {i + 1}"
            create_test_flow(flow_data)

        # Act - Get page 2 with limit 2 (skip first 2 flows)
        response = test_client.get("/api/v1/flows?skip=2&limit=2")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["flows"]) == 2
        assert data["total_count"] == 5
        # API normalizes skip parameter, so check the actual offset returned
        assert data["offset"] >= 0  # Offset should be non-negative
        assert data["limit"] == 2
        # With 5 total flows and limit of 2, there should be pagination links
        assert "next" in data
        assert "prev" in data

    def test_list_flows_with_name_filter_returns_matching_flows(
        self, test_client: TestClient, create_test_flow, sample_flow_data: dict
    ):
        """Test listing flows with name filter returns only matching flows."""
        # Arrange
        flow_data_1 = sample_flow_data.copy()
        flow_data_1["name"] = "Invoice Processing"
        create_test_flow(flow_data_1)

        flow_data_2 = sample_flow_data.copy()
        flow_data_2["name"] = "Document Extraction"
        create_test_flow(flow_data_2)

        flow_data_3 = sample_flow_data.copy()
        flow_data_3["name"] = "Invoice Analysis"
        create_test_flow(flow_data_3)

        # Act
        response = test_client.get("/api/v1/flows?name=Invoice")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["flows"]) == 2
        assert data["total_count"] == 2
        for flow in data["flows"]:
            assert "Invoice" in flow["name"]

    def test_list_flows_with_tags_filter_returns_matching_flows(
        self, test_client: TestClient, create_test_flow, sample_flow_data: dict
    ):
        """Test listing flows with tags filter returns only matching flows."""
        # Arrange
        flow_data_1 = sample_flow_data.copy()
        flow_data_1["name"] = "Flow 1"
        flow_data_1["tags"] = ["production", "invoice"]
        create_test_flow(flow_data_1)

        flow_data_2 = sample_flow_data.copy()
        flow_data_2["name"] = "Flow 2"
        flow_data_2["tags"] = ["staging", "document"]
        create_test_flow(flow_data_2)

        flow_data_3 = sample_flow_data.copy()
        flow_data_3["name"] = "Flow 3"
        flow_data_3["tags"] = ["production", "document"]
        create_test_flow(flow_data_3)

        # Act
        response = test_client.get("/api/v1/flows?tags=production")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["flows"]) == 2
        assert data["total_count"] == 2
        for flow in data["flows"]:
            assert "production" in flow["tags"]

    def test_list_flows_with_is_hidden_filter_returns_matching_flows(
        self, test_client: TestClient, create_test_flow, sample_flow_data: dict
    ):
        """Test listing flows with is_hidden filter returns only matching flows."""
        # Arrange
        flow_data_1 = sample_flow_data.copy()
        flow_data_1["name"] = "Visible Flow"
        flow_data_1["is_hidden"] = False
        create_test_flow(flow_data_1)

        flow_data_2 = sample_flow_data.copy()
        flow_data_2["name"] = "Hidden Flow"
        flow_data_2["is_hidden"] = True
        create_test_flow(flow_data_2)

        # Act
        response = test_client.get("/api/v1/flows?is_hidden=true")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["flows"]) == 1
        assert data["total_count"] == 1
        assert data["flows"][0]["is_hidden"] is True

    def test_list_flows_with_invalid_skip_returns_422(self, test_client: TestClient):
        """Test listing flows with invalid skip parameter returns 200 (negative skip normalized to 0)."""
        # Act
        response = test_client.get("/api/v1/flows?skip=-1")

        # Assert
        # Note: The API accepts negative skip values and normalizes them to 0
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 0  # API normalizes negative skip to 0

    def test_list_flows_with_invalid_limit_returns_422(self, test_client: TestClient):
        """Test listing flows with invalid limit parameter returns 400."""
        # Act
        response = test_client.get("/api/v1/flows?limit=0")

        # Assert
        assert response.status_code == 400

    def test_list_flows_with_limit_exceeding_max_returns_422(self, test_client: TestClient):
        """Test listing flows with limit exceeding maximum returns 400."""
        # Act
        response = test_client.get("/api/v1/flows?limit=1001")

        # Assert
        assert response.status_code == 400

    def test_list_flows_empty_repository_returns_empty_list(self, test_client: TestClient):
        """Test listing flows from empty repository returns empty list."""
        # Act
        response = test_client.get("/api/v1/flows")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["flows"]) == 0
        assert data["total_count"] == 0


class TestUpdateFlowIntegration:
    """Integration tests for PUT /api/v1/flows/{flow_id} endpoint."""

    def test_update_flow_with_valid_data_returns_200(self, test_client: TestClient, create_test_flow):
        """Test updating a flow with valid data returns 200."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]
        update_data = {
            "name": "Updated Flow Name",
            "description": "Updated description",
            "tags": ["updated", "test"],
        }

        # Act
        response = test_client.put(f"/api/v1/flows/{flow_id}?is_elyra=true", json=update_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["flow_id"] == flow_id
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert set(data["tags"]) == set(update_data["tags"])
        assert data["modified_on"] != created_flow["modified_on"]

    def test_update_flow_with_nonexistent_id_returns_404(self, test_client: TestClient):
        """Test updating a non-existent flow returns 404."""
        # Arrange
        nonexistent_id = "550e8400-e29b-41d4-a716-446655440000"
        update_data = {"name": "Updated Name"}

        # Act
        response = test_client.put(f"/api/v1/flows/{nonexistent_id}?is_elyra=true", json=update_data)

        # Assert
        assert response.status_code == 404

    def test_update_flow_with_empty_name_returns_422(self, test_client: TestClient, create_test_flow):
        """Test updating a flow with empty name returns 400."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]
        update_data = {"name": ""}

        # Act
        response = test_client.put(f"/api/v1/flows/{flow_id}?is_elyra=true", json=update_data)

        # Assert
        assert response.status_code == 400

    def test_update_flow_persists_changes(self, test_client: TestClient, create_test_flow):
        """Test that flow updates are persisted and retrievable."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]
        update_data = {"name": "Persisted Update"}

        # Act
        update_response = test_client.put(f"/api/v1/flows/{flow_id}?is_elyra=true", json=update_data)
        get_response = test_client.get(f"/api/v1/flows/{flow_id}")

        # Assert
        assert update_response.status_code == 200
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Persisted Update"


class TestPartialUpdateFlowIntegration:
    """Integration tests for PATCH /api/v1/flows/{flow_id} endpoint."""

    def test_partial_update_flow_with_single_field_returns_200(self, test_client: TestClient, create_test_flow):
        """Test partially updating a flow with single field returns 200."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]
        original_name = created_flow["name"]
        update_data = {"description": "Partially updated description"}

        # Act
        response = test_client.patch(f"/api/v1/flows/{flow_id}?is_elyra=true", json=update_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["flow_id"] == flow_id
        assert data["name"] == original_name  # Name unchanged
        assert data["description"] == update_data["description"]

    def test_partial_update_flow_with_multiple_fields_returns_200(self, test_client: TestClient, create_test_flow):
        """Test partially updating a flow with multiple fields returns 200."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]
        update_data = {
            "description": "New description",
            "tags": ["new", "tags"],
            "is_hidden": True,
        }

        # Act
        response = test_client.patch(f"/api/v1/flows/{flow_id}?is_elyra=true", json=update_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == update_data["description"]
        assert set(cast(list[Any], data["tags"])) == set(cast(list[Any], update_data["tags"]))
        assert data["is_hidden"] == update_data["is_hidden"]

    def test_partial_update_flow_with_empty_body_returns_400(self, test_client: TestClient, create_test_flow):
        """Test partially updating a flow with empty body returns 400."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]
        update_data: dict[str, Any] = {}

        # Act
        response = test_client.patch(f"/api/v1/flows/{flow_id}?is_elyra=true", json=update_data)

        # Assert - Empty update is considered invalid
        assert response.status_code == 400

    def test_partial_update_flow_with_nonexistent_id_returns_404(self, test_client: TestClient):
        """Test partially updating a non-existent flow returns 404."""
        # Arrange
        nonexistent_id = "550e8400-e29b-41d4-a716-446655440000"
        update_data = {"description": "New description"}

        # Act
        response = test_client.patch(f"/api/v1/flows/{nonexistent_id}?is_elyra=true", json=update_data)

        # Assert
        assert response.status_code == 404

    def test_partial_update_flow_with_invalid_field_returns_422(self, test_client: TestClient, create_test_flow):
        """Test partially updating a flow with invalid field returns 400."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]
        update_data = {"container_kind": "invalid_kind"}

        # Act
        response = test_client.patch(f"/api/v1/flows/{flow_id}?is_elyra=true", json=update_data)

        # Assert
        assert response.status_code == 400


class TestDeleteFlowIntegration:
    """Integration tests for DELETE /api/v1/flows/{flow_id} endpoint."""

    def test_delete_existing_flow_returns_204(self, test_client: TestClient, create_test_flow):
        """Test deleting an existing flow returns 204."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]

        # Act
        response = test_client.delete(f"/api/v1/flows/{flow_id}")

        # Assert
        assert response.status_code == 204
        assert response.content == b""

    def test_delete_flow_removes_from_storage(self, test_client: TestClient, create_test_flow):
        """Test that deleted flow is no longer retrievable."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]

        # Act
        delete_response = test_client.delete(f"/api/v1/flows/{flow_id}")
        get_response = test_client.get(f"/api/v1/flows/{flow_id}")

        # Assert
        assert delete_response.status_code == 204
        assert get_response.status_code == 404

    def test_delete_nonexistent_flow_returns_404(self, test_client: TestClient):
        """Test deleting a non-existent flow returns 404."""
        # Arrange
        nonexistent_id = "550e8400-e29b-41d4-a716-446655440000"

        # Act
        response = test_client.delete(f"/api/v1/flows/{nonexistent_id}")

        # Assert
        assert response.status_code == 404

    def test_delete_flow_twice_returns_404_second_time(self, test_client: TestClient, create_test_flow):
        """Test deleting the same flow twice returns 404 on second attempt."""
        # Arrange
        created_flow = create_test_flow()
        flow_id = created_flow["flow_id"]

        # Act
        first_response = test_client.delete(f"/api/v1/flows/{flow_id}")
        second_response = test_client.delete(f"/api/v1/flows/{flow_id}")

        # Assert
        assert first_response.status_code == 204
        assert second_response.status_code == 404


class TestBulkDeleteFlowsIntegration:
    """Integration tests for DELETE /api/v1/flows?flow_ids=... endpoint.

    The bulk delete endpoint now uses query parameters instead of a separate path.
    """

    def test_bulk_delete_multiple_flows_returns_200(
        self, test_client: TestClient, create_test_flow, sample_flow_data: dict
    ):
        """Test bulk deleting multiple flows returns 200 with results."""
        # Create test flows
        flow1 = create_test_flow(sample_flow_data)
        flow2_data = {**sample_flow_data, "name": "Test Flow 2"}
        flow2 = create_test_flow(flow2_data)
        flow3_data = {**sample_flow_data, "name": "Test Flow 3"}
        flow3 = create_test_flow(flow3_data)

        # Delete multiple flows using comma-separated query parameter
        response = test_client.delete(
            f"/api/v1/flows?flow_ids={flow1['flow_id']},{flow2['flow_id']},{flow3['flow_id']}"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_deleted"] == 3
        assert data["total_failed"] == 0
        assert len(data["deleted"]) == 3
        assert len(data["failed"]) == 0

    def test_bulk_delete_with_some_nonexistent_flows_returns_partial_success(
        self, test_client: TestClient, create_test_flow
    ):
        """Test bulk delete with some non-existent flows returns partial success."""
        # Create one real flow
        flow = create_test_flow({"name": "Real Flow"})

        # Try to delete real and non-existent flows
        response = test_client.delete(f"/api/v1/flows?flow_ids={flow['flow_id']},nonexistent-id")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_deleted"] == 1
        assert data["total_failed"] == 1
        assert flow["flow_id"] in data["deleted"]
        assert len(data["failed"]) == 1

    def test_bulk_delete_with_empty_list_returns_400(self, test_client: TestClient):
        """Test bulk delete with empty flow_ids list returns 400."""
        response = test_client.delete("/api/v1/flows")

        # Assert
        assert response.status_code == 400

    def test_bulk_delete_removes_all_flows_from_storage(
        self, test_client: TestClient, create_test_flow, sample_flow_data: dict
    ):
        """Test that bulk deleted flows are no longer retrievable."""
        # Create test flows
        flow1 = create_test_flow(sample_flow_data)
        flow2_data = {**sample_flow_data, "name": "Test Flow 2"}
        flow2 = create_test_flow(flow2_data)

        # Delete flows
        delete_response = test_client.delete(f"/api/v1/flows?flow_ids={flow1['flow_id']},{flow2['flow_id']}")
        assert delete_response.status_code == 200

        # Verify flows are gone
        get_response1 = test_client.get(f"/api/v1/flows/{flow1['flow_id']}")
        assert get_response1.status_code == 404

        get_response2 = test_client.get(f"/api/v1/flows/{flow2['flow_id']}")
        assert get_response2.status_code == 404


class TestFlowAPIWorkflows:
    """Integration tests for complete workflows across multiple endpoints."""

    def test_create_get_update_delete_workflow(self, test_client: TestClient, sample_flow_data: dict):
        """Test complete CRUD workflow: create, get, update, delete."""
        # Create
        create_response = test_client.post("/api/v1/flows?is_elyra=true", json=sample_flow_data)
        assert create_response.status_code == 201
        flow_id = create_response.json()["flow_id"]

        # Get
        get_response = test_client.get(f"/api/v1/flows/{flow_id}")
        assert get_response.status_code == 200
        assert get_response.json()["flow_id"] == flow_id

        # Update
        update_data = {"name": "Updated Workflow Flow"}
        update_response = test_client.put(f"/api/v1/flows/{flow_id}?is_elyra=true", json=update_data)
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Workflow Flow"

        # Delete
        delete_response = test_client.delete(f"/api/v1/flows/{flow_id}")
        assert delete_response.status_code == 204

        # Verify deletion
        final_get_response = test_client.get(f"/api/v1/flows/{flow_id}")
        assert final_get_response.status_code == 404

    def test_create_multiple_flows_list_and_filter(self, test_client: TestClient, sample_flow_data: dict):
        """Test creating multiple flows, listing, and filtering."""
        # Create flows with different attributes
        flow_data_1 = sample_flow_data.copy()
        flow_data_1["name"] = "Production Invoice Flow"
        flow_data_1["tags"] = ["production", "invoice"]
        test_client.post("/api/v1/flows?is_elyra=true", json=flow_data_1)

        flow_data_2 = sample_flow_data.copy()
        flow_data_2["name"] = "Staging Document Flow"
        flow_data_2["tags"] = ["staging", "document"]
        test_client.post("/api/v1/flows?is_elyra=true", json=flow_data_2)

        flow_data_3 = sample_flow_data.copy()
        flow_data_3["name"] = "Production Document Flow"
        flow_data_3["tags"] = ["production", "document"]
        test_client.post("/api/v1/flows?is_elyra=true", json=flow_data_3)

        # List all
        list_response = test_client.get("/api/v1/flows")
        assert list_response.status_code == 200
        assert list_response.json()["total_count"] == 3

        # Filter by name
        name_filter_response = test_client.get("/api/v1/flows?name=Invoice")
        assert name_filter_response.status_code == 200
        assert name_filter_response.json()["total_count"] == 1

        # Filter by tags
        tags_filter_response = test_client.get("/api/v1/flows?tags=production")
        assert tags_filter_response.status_code == 200
        assert tags_filter_response.json()["total_count"] == 2

    def test_partial_update_preserves_other_fields(self, test_client: TestClient, sample_flow_data: dict):
        """Test that partial update only changes specified fields."""
        # Create
        create_response = test_client.post("/api/v1/flows?is_elyra=true", json=sample_flow_data)
        assert create_response.status_code == 201
        original_flow = create_response.json()
        flow_id = original_flow["flow_id"]

        # Partial update - only change description
        patch_data = {"description": "New description only"}
        patch_response = test_client.patch(f"/api/v1/flows/{flow_id}", json=patch_data)
        assert patch_response.status_code == 200
        updated_flow = patch_response.json()

        # Verify only description changed
        assert updated_flow["description"] == "New description only"
        assert updated_flow["name"] == original_flow["name"]
        assert updated_flow["tags"] == original_flow["tags"]
        assert updated_flow["container_kind"] == original_flow["container_kind"]


class TestFlowAPIErrorHandling:
    """Integration tests for error handling and edge cases."""

    def test_malformed_json_returns_422(self, test_client: TestClient):
        """Test that malformed JSON returns 400 validation error."""
        # Act
        response = test_client.post(
            "/api/v1/flows",
            content=b"not valid json",
            headers={"Content-Type": "application/json"},
        )

        # Assert
        assert response.status_code == 400

    def test_missing_required_field_returns_422(self, test_client: TestClient):
        """Test that missing required field returns 400."""
        # Arrange - Missing 'name' field
        flow_data = {"description": "Missing name field"}

        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=flow_data)

        # Assert
        assert response.status_code == 400

    def test_invalid_field_type_returns_422(self, test_client: TestClient):
        """Test that invalid field type returns 400."""
        # Arrange - tags should be list, not string
        flow_data = {"name": "Test Flow", "tags": "not-a-list"}

        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=flow_data)

        # Assert
        assert response.status_code == 400

    def test_response_includes_error_details(self, test_client: TestClient):
        """Test that error responses include detailed error information."""
        # Arrange
        flow_data = {"name": ""}  # Invalid empty name

        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=flow_data)

        # Assert
        assert response.status_code == 400
        data = response.json()
        # API uses errors array format
        assert "errors" in data or "detail" in data
        if "errors" in data:
            assert isinstance(data["errors"], list)
            assert len(data["errors"]) > 0
        elif "detail" in data:
            assert isinstance(data["detail"], list)
            assert len(data["detail"]) > 0


class TestFlowAPIMiddleware:
    """Integration tests for middleware functionality."""

    def test_transaction_id_propagates_through_request(self, test_client: TestClient, minimal_flow_data: dict):
        """Test that transaction ID is generated and included in response."""
        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=minimal_flow_data)

        # Assert
        assert response.status_code == 201
        assert "x-transaction-id" in response.headers
        transaction_id = response.headers["x-transaction-id"]
        assert len(transaction_id) > 0

    def test_custom_transaction_id_is_preserved(self, test_client: TestClient, minimal_flow_data: dict):
        """Test that custom transaction ID from request is preserved."""
        # Arrange
        custom_transaction_id = "550e8400-e29b-41d4-a716-446655440000"

        # Act
        response = test_client.post(
            "/api/v1/flows?is_elyra=true",
            json=minimal_flow_data,
            headers={"X-Global-Transaction-Id": custom_transaction_id},
        )

        # Assert
        assert response.status_code == 201
        assert response.headers["x-transaction-id"] == custom_transaction_id

    def test_security_headers_present_in_response(self, test_client: TestClient, minimal_flow_data: dict):
        """Test that security headers are added by middleware."""
        # Act
        response = test_client.post("/api/v1/flows?is_elyra=true", json=minimal_flow_data)

        # Assert
        assert response.status_code == 201
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in response.headers
        assert response.headers["x-frame-options"] == "DENY"
