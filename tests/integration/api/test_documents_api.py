"""Integration tests for document retrieval API endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from docpipe.api.auth.dependencies import get_current_user
from docpipe.api.auth.models import User
from docpipe.api.main import app
from docpipe.api.services.opensearch_service import get_opensearch_service


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    return User(
        username="john.doe",
        email="john.doe@example.com",
        full_name="John Doe",
    )


@pytest.fixture
def mock_opensearch_service():
    """Mock OpenSearch service for testing."""
    service = MagicMock()

    # Mock config
    service.config.opensearch_default_index = "documents"

    # Mock client
    mock_client = MagicMock()
    service.get_client.return_value = mock_client

    return service, mock_client


@pytest.fixture
def authenticated_client(mock_user, mock_opensearch_service):
    """Create a test client with mocked authentication and OpenSearch."""
    service, mock_client = mock_opensearch_service

    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_opensearch_service] = lambda: service

    client = TestClient(app)

    yield client, mock_user, service, mock_client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client():
    """Create a test client without authentication."""
    # Clear any existing overrides
    app.dependency_overrides.clear()
    return TestClient(app)


class TestGetDocument:
    """Test suite for GET /api/v1/documents/{document_id} endpoint."""

    def test_get_document_success(self, authenticated_client):
        """Test successful document retrieval."""
        client, _mock_user, _service, mock_client = authenticated_client

        # Mock OpenSearch response
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc-123",
                        "_source": {
                            "content": "Test document content",
                            "metadata": {"category": "tech", "title": "Test Document"},
                            "allowed_users": ["john.doe"],
                            "created_at": "2026-05-01T10:00:00Z",
                        },
                    }
                ]
            }
        }

        response = client.get(
            "/api/v1/documents/doc-123",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "doc-123"
        assert data["content"] == "Test document content"
        assert data["metadata"]["title"] == "Test Document"
        assert "allowed_users" not in data

    def test_get_document_not_found(self, authenticated_client):
        """Test document not found returns 404."""
        client, _mock_user, _service, mock_client = authenticated_client
        mock_client.search.return_value = {"hits": {"hits": []}}

        response = client.get(
            "/api/v1/documents/nonexistent",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_document_unauthorized_user(self, authenticated_client):
        """Test user not in allowed_users returns 404."""
        client, _mock_user, _service, mock_client = authenticated_client
        # Mock OpenSearch to return no results (ACL filter blocks access)
        mock_client.search.return_value = {"hits": {"hits": []}}

        response = client.get(
            "/api/v1/documents/doc-123",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_document_no_auth(self, unauthenticated_client):
        """Test request without authentication returns 401."""
        response = unauthenticated_client.get("/api/v1/documents/doc-123")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_document_invalid_token(self, unauthenticated_client):
        """Test request with invalid token returns 401."""
        response = unauthenticated_client.get(
            "/api/v1/documents/doc-123",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestSearchDocuments:
    """Test suite for POST /api/v1/documents/search endpoint."""

    def test_search_documents_success(self, authenticated_client):
        """Test successful document search."""
        client, _mock_user, _service, mock_client = authenticated_client
        mock_client.search.return_value = {
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {
                        "_id": "doc-1",
                        "_source": {
                            "content": "Machine learning content",
                            "title": "ML Guide",
                            "metadata": {"category": "tech"},
                            "allowed_users": ["john.doe"],
                        },
                    },
                    {
                        "_id": "doc-2",
                        "_source": {
                            "content": "AI content",
                            "title": "AI Basics",
                            "metadata": {"category": "tech"},
                            "allowed_users": ["john.doe"],
                        },
                    },
                ],
            }
        }

        response = client.post(
            "/api/v1/documents/search",
            headers={"Authorization": "Bearer mock_token"},
            json={"query": "machine learning", "limit": 10, "offset": 0},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["documents"]) == 2
        assert data["total"] == 2
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert data["has_more"] is False

    def test_search_documents_with_filters(self, authenticated_client):
        """Test search with field filters."""
        client, _mock_user, _service, mock_client = authenticated_client
        mock_client.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "doc-1",
                        "_source": {
                            "content": "Tech content",
                            "title": "Tech Doc",
                            "metadata": {"category": "tech"},
                            "allowed_users": ["john.doe"],
                        },
                    }
                ],
            }
        }

        response = client.post(
            "/api/v1/documents/search",
            headers={"Authorization": "Bearer mock_token"},
            json={
                "query": "technology",
                "filters": {"category": "tech"},
                "limit": 10,
                "offset": 0,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["documents"]) == 1

    def test_search_documents_with_sort(self, authenticated_client):
        """Test search with sorting."""
        client, _mock_user, _service, mock_client = authenticated_client
        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        response = client.post(
            "/api/v1/documents/search",
            headers={"Authorization": "Bearer mock_token"},
            json={
                "sort": [{"created_at": "desc"}],
                "limit": 10,
                "offset": 0,
            },
        )

        assert response.status_code == status.HTTP_200_OK

    def test_search_documents_pagination(self, authenticated_client):
        """Test search pagination."""
        client, _mock_user, _service, mock_client = authenticated_client
        mock_client.search.return_value = {
            "hits": {
                "total": {"value": 100},
                "hits": [
                    {
                        "_id": f"doc-{i}",
                        "_source": {
                            "content": f"Content {i}",
                            "allowed_users": ["john.doe"],
                        },
                    }
                    for i in range(20)
                ],
            }
        }

        response = client.post(
            "/api/v1/documents/search",
            headers={"Authorization": "Bearer mock_token"},
            json={"limit": 20, "offset": 0},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["documents"]) == 20
        assert data["total"] == 100
        assert data["has_more"] is True

    def test_search_documents_no_results(self, authenticated_client):
        """Test search with no matching documents."""
        client, _mock_user, _service, mock_client = authenticated_client
        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        response = client.post(
            "/api/v1/documents/search",
            headers={"Authorization": "Bearer mock_token"},
            json={"query": "nonexistent", "limit": 10, "offset": 0},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["documents"]) == 0
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_search_documents_no_auth(self, unauthenticated_client):
        """Test search without authentication returns 401."""
        response = unauthenticated_client.post(
            "/api/v1/documents/search",
            json={"query": "test", "limit": 10, "offset": 0},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_documents_invalid_limit(self, authenticated_client):
        """Test search with invalid limit returns 400."""
        client, _mock_user, _service, _mock_client = authenticated_client
        response = client.post(
            "/api/v1/documents/search",
            headers={"Authorization": "Bearer mock_token"},
            json={"limit": 1000, "offset": 0},  # Exceeds max limit of 100
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_documents_negative_offset(self, authenticated_client):
        """Test search with negative offset returns 400."""
        client, _mock_user, _service, _mock_client = authenticated_client
        response = client.post(
            "/api/v1/documents/search",
            headers={"Authorization": "Bearer mock_token"},
            json={"limit": 10, "offset": -1},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
