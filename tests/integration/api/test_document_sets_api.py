"""Integration tests for document sets API endpoints.

Tests the REST API interface for document set operations, validating that
the hexagonal architecture works correctly end-to-end through the API layer.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from docpipe.api.main import app


@pytest.fixture(scope="module")
def client():
    """Create test client for API requests."""
    return TestClient(app)


@pytest.fixture(scope="function")
def temp_db_path(tmp_path):
    """Create unique temporary database path for each test."""
    db_file = tmp_path / f"test_{uuid.uuid4().hex[:8]}.duckdb"
    return str(db_file)


@pytest.fixture(scope="function")
def cleanup_document_sets(client):
    """Clean up test document sets after each test."""
    created_ids = []

    yield created_ids

    # Cleanup: delete all created document sets
    for doc_set_id in created_ids:
        try:
            client.delete(f"/api/v1/document-sets/{doc_set_id}")
        except Exception:
            pass  # Ignore cleanup errors


class TestDocumentSetCRUD:
    """Test CRUD operations for document sets via API."""

    def test_create_document_set(self, client, temp_db_path, cleanup_document_sets):
        """Test creating a document set via POST endpoint."""
        payload = {"name": "api_test_set", "description": "Created via API", "metadata": {"source": "api_test"}}

        response = client.post("/api/v1/document-sets", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "api_test_set"
        assert data["description"] == "Created via API"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["metadata"]["source"] == "api_test"
        assert data["total_documents"] == 0
        assert data["total_size_bytes"] == 0
        assert data["total_pages"] == 0

        cleanup_document_sets.append(data["id"])

    def test_create_document_set_idempotent(self, client, temp_db_path, cleanup_document_sets):
        """Test that creating document set with same name is idempotent."""
        payload = {"name": "idempotent_test_set", "description": "First description"}

        # First creation
        response1 = client.post("/api/v1/document-sets", json=payload)
        assert response1.status_code == 201
        data1 = response1.json()
        cleanup_document_sets.append(data1["id"])

        # Second creation with same name
        payload["description"] = "Different description"
        response2 = client.post("/api/v1/document-sets", json=payload)
        assert response2.status_code == 201
        data2 = response2.json()

        # Should return same document set
        assert data1["id"] == data2["id"]
        assert data1["name"] == data2["name"]
        # Original description should be preserved
        assert data2["description"] == "First description"

    def test_list_document_sets(self, client, temp_db_path, cleanup_document_sets):
        """Test listing all document sets."""
        # Create test document sets
        for i in range(3):
            payload = {"name": f"list_test_set_{i}", "description": f"For list test {i}"}
            response = client.post("/api/v1/document-sets", json=payload)
            cleanup_document_sets.append(response.json()["id"])

        # List all
        response = client.get("/api/v1/document-sets")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) >= 3

        # Verify our test sets are in the list
        names = [item["name"] for item in data["items"]]
        assert "list_test_set_0" in names
        assert "list_test_set_1" in names
        assert "list_test_set_2" in names

    def test_list_with_pagination(self, client, temp_db_path, cleanup_document_sets):
        """Test listing document sets with pagination parameters."""
        # Create test document sets
        for i in range(5):
            payload = {"name": f"pagination_test_{i}"}
            response = client.post("/api/v1/document-sets", json=payload)
            cleanup_document_sets.append(response.json()["id"])

        # Test with limit
        response = client.get("/api/v1/document-sets", params={"limit": 2, "offset": 0})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_get_document_set_by_id(self, client, temp_db_path, cleanup_document_sets):
        """Test getting specific document set by ID."""
        # Create document set
        payload = {"name": "get_test_set", "description": "For GET test", "metadata": {"test": "value"}}
        create_response = client.post("/api/v1/document-sets", json=payload)
        doc_set_id = create_response.json()["id"]
        cleanup_document_sets.append(doc_set_id)

        # Get by ID
        response = client.get(f"/api/v1/document-sets/{doc_set_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == doc_set_id
        assert data["name"] == "get_test_set"
        assert data["description"] == "For GET test"
        assert data["metadata"]["test"] == "value"

    def test_get_nonexistent_document_set(self, client):
        """Test getting nonexistent document set returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/document-sets/{fake_id}")
        assert response.status_code == 404

        error = response.json()
        # API returns error in ErrorResponse format with errors array
        assert "errors" in error
        assert len(error["errors"]) > 0
        assert error["errors"][0]["code"] == "document_set_not_found"

    def test_update_document_set(self, client, temp_db_path, cleanup_document_sets):
        """Test updating document set metadata via PATCH."""
        # Create document set
        payload = {"name": "update_test_set", "description": "Original description", "metadata": {"version": "1.0"}}
        create_response = client.post("/api/v1/document-sets", json=payload)
        doc_set_id = create_response.json()["id"]
        cleanup_document_sets.append(doc_set_id)

        # Update
        update_payload = {"description": "Updated description", "metadata": {"version": "2.0", "updated": True}}
        response = client.patch(f"/api/v1/document-sets/{doc_set_id}", json=update_payload)
        assert response.status_code == 200

        data = response.json()
        assert data["description"] == "Updated description"
        assert data["metadata"]["version"] == "2.0"
        assert data["metadata"]["updated"] is True
        assert data["name"] == "update_test_set"  # Name unchanged

    def test_update_partial_fields(self, client, temp_db_path, cleanup_document_sets):
        """Test partial update (PATCH semantics) only updates provided fields."""
        # Create document set
        payload = {
            "name": "partial_update_test",
            "description": "Original description",
            "metadata": {"key1": "value1", "key2": "value2"},
        }
        create_response = client.post("/api/v1/document-sets", json=payload)
        doc_set_id = create_response.json()["id"]
        cleanup_document_sets.append(doc_set_id)

        # Update only description
        update_payload = {"description": "New description"}
        response = client.patch(f"/api/v1/document-sets/{doc_set_id}", json=update_payload)
        assert response.status_code == 200

        data = response.json()
        assert data["description"] == "New description"
        # Metadata should be unchanged
        assert data["metadata"]["key1"] == "value1"
        assert data["metadata"]["key2"] == "value2"

    def test_delete_document_set(self, client, temp_db_path):
        """Test deleting document set."""
        # Create document set
        payload = {"name": "delete_test_set", "description": "Will be deleted"}
        create_response = client.post("/api/v1/document-sets", json=payload)
        doc_set_id = create_response.json()["id"]

        # Delete
        response = client.delete(f"/api/v1/document-sets/{doc_set_id}")
        assert response.status_code == 204

        # Verify deleted
        get_response = client.get(f"/api/v1/document-sets/{doc_set_id}")
        assert get_response.status_code == 404

    def test_delete_with_data_parameter(self, client, temp_db_path):
        """Test deleting document set with delete_data parameter."""
        # Create document set
        payload = {"name": "delete_data_test"}
        create_response = client.post("/api/v1/document-sets", json=payload)
        doc_set_id = create_response.json()["id"]

        # Delete with explicit delete_data=true
        response = client.delete(f"/api/v1/document-sets/{doc_set_id}", params={"delete_data": True})
        assert response.status_code == 204


class TestDocumentSetData:
    """Test data operations for document sets."""

    @pytest.fixture
    def document_set_with_data(self, client, temp_db_path, cleanup_document_sets):
        """Create document set and add sample data."""
        # Create document set
        payload = {"name": f"data_test_set_{uuid.uuid4().hex[:8]}", "description": "For data operations"}
        create_response = client.post("/api/v1/document-sets", json=payload)
        doc_set_id = create_response.json()["id"]
        cleanup_document_sets.append(doc_set_id)

        return doc_set_id

    def test_preview_empty_document_set(self, document_set_with_data, client):
        """Test previewing document set with no data."""
        response = client.get(f"/api/v1/document-sets/{document_set_with_data}/preview")
        assert response.status_code == 200

        data = response.json()
        assert "columns" in data
        assert "data" in data
        assert "total_rows" in data
        assert data["total_rows"] == 0
        assert len(data["data"]) == 0

    def test_preview_with_pagination(self, document_set_with_data, client):
        """Test previewing data with pagination parameters."""
        response = client.get(
            f"/api/v1/document-sets/{document_set_with_data}/preview", params={"limit": 5, "offset": 0}
        )
        assert response.status_code == 200

        data = response.json()
        assert "columns" in data
        assert "data" in data
        assert "total_rows" in data


class TestDocumentSetValidation:
    """Test validation and error handling."""

    def test_create_with_missing_name(self, client):
        """Test creating document set without required name field."""
        payload = {"description": "Missing name"}
        response = client.post("/api/v1/document-sets", json=payload)
        # Accept both 400 and 422 as valid validation error codes
        assert response.status_code in [400, 422]

    def test_create_with_empty_name(self, client):
        """Test creating document set with empty name."""
        payload = {"name": "", "description": "Empty name"}
        response = client.post("/api/v1/document-sets", json=payload)
        assert response.status_code in [400, 422]

    def test_create_with_invalid_name_pattern(self, client):
        """Test creating document set with invalid name pattern."""
        payload = {
            "name": "\x00invalid\x01name",  # Control characters
            "description": "Invalid name",
        }
        response = client.post("/api/v1/document-sets", json=payload)
        assert response.status_code in [400, 422]

    def test_create_with_too_long_name(self, client):
        """Test creating document set with name exceeding max length."""
        payload = {
            "name": "a" * 300,  # Exceeds 256 char limit
            "description": "Too long name",
        }
        response = client.post("/api/v1/document-sets", json=payload)
        assert response.status_code in [400, 422]

    def test_create_with_too_long_description(self, client, cleanup_document_sets):
        """Test creating document set with description exceeding max length."""
        payload = {
            "name": "long_desc_test",
            "description": "a" * 15000,  # Exceeds 10000 char limit
        }
        response = client.post("/api/v1/document-sets", json=payload)
        assert response.status_code in [400, 422]

    def test_get_with_invalid_uuid(self, client):
        """Test getting document set with invalid UUID format."""
        response = client.get("/api/v1/document-sets/not-a-valid-uuid")
        assert response.status_code in [400, 422]

    def test_update_nonexistent_document_set(self, client):
        """Test updating nonexistent document set returns 404."""
        fake_id = str(uuid.uuid4())
        payload = {"description": "Updated"}
        response = client.patch(f"/api/v1/document-sets/{fake_id}", json=payload)
        assert response.status_code == 404
        # Don't validate error response structure - just check status code

    def test_delete_nonexistent_document_set(self, client):
        """Test deleting nonexistent document set returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/document-sets/{fake_id}")
        assert response.status_code == 404
        # Don't validate error response structure - just check status code

    def test_preview_nonexistent_document_set(self, client):
        """Test previewing nonexistent document set returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/document-sets/{fake_id}/preview")
        assert response.status_code == 404
        # Don't validate error response structure - just check status code


class TestDocumentSetResponseSchema:
    """Test response schema compliance."""

    def test_create_response_schema(self, client, temp_db_path, cleanup_document_sets):
        """Test that create response contains all required fields."""
        payload = {"name": "schema_test_set", "description": "Testing response schema", "metadata": {"key": "value"}}

        response = client.post("/api/v1/document-sets", json=payload)
        assert response.status_code == 201

        data = response.json()
        cleanup_document_sets.append(data["id"])

        # Required fields
        assert "id" in data
        assert "name" in data
        assert "storage_backend" in data
        assert "database_path" in data
        assert "table_name" in data
        assert "total_documents" in data
        assert "total_size_bytes" in data
        assert "total_pages" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "metadata" in data

        # Optional fields
        assert "description" in data

        # Verify types
        assert isinstance(data["id"], str)
        assert isinstance(data["name"], str)
        assert isinstance(data["total_documents"], int)
        assert isinstance(data["total_size_bytes"], int)
        assert isinstance(data["total_pages"], int)
        assert isinstance(data["metadata"], dict)

    def test_list_response_schema(self, client):
        """Test that list response contains pagination fields."""
        response = client.get("/api/v1/document-sets")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["limit"], int)
        assert isinstance(data["offset"], int)

    def test_preview_response_schema(self, client, temp_db_path, cleanup_document_sets):
        """Test that preview response contains required fields."""
        # Create document set
        payload = {"name": "preview_schema_test"}
        create_response = client.post("/api/v1/document-sets", json=payload)
        doc_set_id = create_response.json()["id"]
        cleanup_document_sets.append(doc_set_id)

        # Preview
        response = client.get(f"/api/v1/document-sets/{doc_set_id}/preview")
        assert response.status_code == 200

        data = response.json()
        assert "columns" in data
        assert "data" in data
        assert "total_rows" in data

        assert isinstance(data["columns"], list)
        assert isinstance(data["data"], list)
        assert isinstance(data["total_rows"], int)


class TestDocumentSetEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_create_with_special_characters_in_name(self, client, cleanup_document_sets):
        """Test creating document set with special characters in name."""
        payload = {"name": "Test_Set-2024 (v1)", "description": "Special chars test"}

        response = client.post("/api/v1/document-sets", json=payload)
        # May fail validation depending on name pattern rules
        if response.status_code == 201:
            data = response.json()
            cleanup_document_sets.append(data["id"])
            assert data["name"] == "Test_Set-2024 (v1)"
            # Table name should be sanitized
            assert data["table_name"] == "test_set_2024_v1"
        else:
            # Validation error is acceptable for special characters
            assert response.status_code in [400, 422]

    def test_create_with_unicode_characters(self, client, cleanup_document_sets):
        """Test creating document set with Unicode characters."""
        payload = {"name": "Test Set 文档集", "description": "Unicode test with 中文"}

        response = client.post("/api/v1/document-sets", json=payload)
        # May fail validation depending on name pattern rules
        if response.status_code == 201:
            data = response.json()
            cleanup_document_sets.append(data["id"])
            assert "文档集" in data["name"]
        else:
            # Validation error is acceptable for unicode characters
            assert response.status_code in [400, 422]

    def test_create_with_null_metadata(self, client, cleanup_document_sets):
        """Test creating document set with null metadata."""
        payload = {"name": "null_metadata_test", "metadata": None}

        response = client.post("/api/v1/document-sets", json=payload)
        assert response.status_code == 201

        data = response.json()
        cleanup_document_sets.append(data["id"])
        # Should default to empty dict
        assert data["metadata"] == {}

    def test_update_with_empty_metadata(self, client, temp_db_path, cleanup_document_sets):
        """Test updating document set with empty metadata dict."""
        # Create with metadata
        payload = {"name": "empty_metadata_test", "metadata": {"key": "value"}}
        create_response = client.post("/api/v1/document-sets", json=payload)
        doc_set_id = create_response.json()["id"]
        cleanup_document_sets.append(doc_set_id)

        # Update with empty metadata
        update_payload = {"metadata": {}}
        response = client.patch(f"/api/v1/document-sets/{doc_set_id}", json=update_payload)
        assert response.status_code == 200

        data = response.json()
        assert data["metadata"] == {}

    def test_list_with_zero_limit(self, client):
        """Test listing with invalid zero limit."""
        response = client.get("/api/v1/document-sets", params={"limit": 0})
        assert response.status_code in [400, 422]  # Validation error

    def test_list_with_negative_offset(self, client):
        """Test listing with invalid negative offset."""
        response = client.get("/api/v1/document-sets", params={"offset": -1})
        assert response.status_code in [400, 422]  # Validation error

    def test_preview_with_zero_limit(self, client, temp_db_path, cleanup_document_sets):
        """Test preview with invalid zero limit."""
        payload = {"name": "preview_zero_limit_test"}
        create_response = client.post("/api/v1/document-sets", json=payload)
        doc_set_id = create_response.json()["id"]
        cleanup_document_sets.append(doc_set_id)

        response = client.get(f"/api/v1/document-sets/{doc_set_id}/preview", params={"limit": 0})
        assert response.status_code in [400, 422]  # Validation error


class TestDocumentSetConcurrency:
    """Test concurrent operations and race conditions."""

    def test_concurrent_create_same_name(self, client, cleanup_document_sets):
        """Test that concurrent creates with same name are handled correctly."""
        payload = {"name": "concurrent_test_set", "description": "Testing concurrent creation"}

        # First creation
        response1 = client.post("/api/v1/document-sets", json=payload)
        assert response1.status_code == 201
        data1 = response1.json()
        cleanup_document_sets.append(data1["id"])

        # Second creation (simulating race condition)
        response2 = client.post("/api/v1/document-sets", json=payload)
        assert response2.status_code == 201
        data2 = response2.json()

        # Should return same document set (idempotent)
        assert data1["id"] == data2["id"]
