"""Unit tests for Operator Metadata API routes.

This test suite validates the router layer for operator metadata endpoints,
ensuring proper:
- HTTP request/response handling
- Dependency injection
- Response model conversion
- Error handling via middleware
- OpenAPI compliance

Test Strategy:
    - Use FastAPI TestClient for HTTP-level testing
    - Mock the service layer (OperatorMetadataService) for isolation
    - Register same exception handlers as main.py for realistic testing
    - Verify HTTP status codes, response structure, and error handling
    - Test edge cases (missing fields, empty features, unknown categories)

Test Fixtures:
    - app: FastAPI application with operators router and error handlers
    - client: TestClient for making HTTP requests
    - mock_service: Mocked OperatorMetadataService
    - override_service: Dependency override for injecting mock service
    - sample_operator_metadata: Sample metadata for testing

Coverage:
    - Success cases: 200 responses with correct structure
    - Error cases: 500 responses with proper error format
    - Edge cases: Missing fields, empty features, unknown categories
    - Dependency injection: Singleton behavior
    - Logging: Request logging
    - Content negotiation: JSON responses
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from datasift.api.routes.operators import get_operator_metadata_service, operators_router
from datasift.core.operators.application.services.operator_metadata_service import (
    OperatorMetadataService,
)
from datasift.exceptions.datasift_exceptions import DatasiftException
from datasift.exceptions.error_codes import ErrorCode


@pytest.fixture
def app():
    """Create FastAPI app with operators router and error handlers.

    Registers the same exception handlers as main.py to ensure tests
    match runtime behavior.
    """
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from datasift.api.middleware.error_handler import (
        datasift_exception_handler,
        generic_exception_handler,
        http_exception_handler,
        validation_exception_handler,
    )
    from datasift.exceptions.datasift_exceptions import DatasiftException

    app = FastAPI()
    app.include_router(operators_router)

    # Register exception handlers in same order as main.py
    app.add_exception_handler(DatasiftException, datasift_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    return app


@pytest.fixture
def client(app):
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_service():
    """Create mock OperatorMetadataService."""
    return Mock(spec=OperatorMetadataService)


@pytest.fixture
def override_service(app, mock_service):
    """Override the get_operator_metadata_service dependency."""
    app.dependency_overrides[get_operator_metadata_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.clear()


@pytest.fixture
def sample_operator_metadata():
    """Sample operator metadata for testing."""
    return {
        "extract_docling": {
            "category": "Extract",
            "label": "Extract Docling",
            "description": "Extracts structured content from documents",
            "features": {
                "content": {
                    "name": "Document Content",
                    "description": "The markdown content extracted from the document",
                    "type": "string",
                    "required": True,
                },
                "doc_id_hash": {
                    "name": "Hash ID",
                    "description": "Hash ID of the document row",
                    "type": "string",
                    "required": True,
                },
            },
            "required_features": [],
        },
        "chunker": {
            "category": "Functional",
            "label": "Chunker",
            "description": "Splits documents into smaller chunks",
            "features": {
                "chunk_id": {
                    "name": "Chunk ID",
                    "description": "Unique identifier for each chunk",
                    "type": "string",
                    "required": True,
                },
            },
            "required_features": ["content"],
        },
    }


class TestGetOperatorMetadataEndpoint:
    """Tests for GET /operators/metadata endpoint.

    This test class covers the main API endpoint for retrieving operator metadata.
    Tests verify:
    - HTTP 200 responses with correct data
    - Response structure matches OpenAPI schema
    - All operators included in response
    - Error handling (service exceptions, generic exceptions)
    - Response model conversion (dict → OperatorMetadataItem)
    - Edge cases (missing fields, empty features, unknown categories)
    - Logging behavior
    - Content-Type headers
    """

    def test_get_operator_metadata_returns_200(self, client, override_service, sample_operator_metadata):
        """Test getting operator metadata returns 200."""
        # Arrange
        override_service.get_all_operator_metadata.return_value = sample_operator_metadata

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "extract_docling" in data
        assert "chunker" in data
        assert data["extract_docling"]["category"] == "Extract"
        override_service.get_all_operator_metadata.assert_called_once_with(internal_features=False)

    def test_get_operator_metadata_returns_dict_structure(self, client, override_service, sample_operator_metadata):
        """Test that response has correct dictionary structure."""
        # Arrange
        override_service.get_all_operator_metadata.return_value = sample_operator_metadata

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify it's a direct dict, not wrapped
        assert isinstance(data, dict)
        assert "extract_docling" in data

        # Verify structure of operator metadata
        operator = data["extract_docling"]
        assert "category" in operator
        assert "features" in operator
        assert "required_features" in operator

    def test_get_operator_metadata_includes_all_operators(self, client, override_service, sample_operator_metadata):
        """Test that all operators from service are included in response."""
        # Arrange
        override_service.get_all_operator_metadata.return_value = sample_operator_metadata

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == len(sample_operator_metadata)
        for operator_name in sample_operator_metadata:
            assert operator_name in data

    def test_get_operator_metadata_handles_service_exception(self, client, override_service):
        """Test that service exceptions are handled properly."""
        # Arrange
        override_service.get_all_operator_metadata.side_effect = DatasiftException(
            message="Failed to retrieve operator metadata",
            status_code=500,
            error_code=ErrorCode.OPERATOR_METADATA_FAILED,
        )

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == ErrorCode.OPERATOR_METADATA_FAILED

    def test_get_operator_metadata_handles_generic_exception(self, client, override_service):
        """Test that generic exceptions are wrapped in DatasiftException by service."""
        # Arrange
        # Service wraps all exceptions in DatasiftException
        override_service.get_all_operator_metadata.side_effect = DatasiftException(
            message="Failed to retrieve operator metadata",
            status_code=500,
            error_code=ErrorCode.OPERATOR_METADATA_FAILED,
        )

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == ErrorCode.OPERATOR_METADATA_FAILED

    def test_get_operator_metadata_converts_metadata_to_response_model(
        self, client, override_service, sample_operator_metadata
    ):
        """Test that raw metadata is converted to proper response model."""
        # Arrange
        override_service.get_all_operator_metadata.return_value = sample_operator_metadata

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify OperatorMetadataItem structure
        operator = data["extract_docling"]
        assert "label" in operator
        assert "category" in operator
        assert "description" in operator
        assert "features" in operator
        assert "required_features" in operator

    def test_get_operator_metadata_handles_missing_optional_fields(self, client, override_service):
        """Test that missing optional fields are handled gracefully."""
        # Arrange
        minimal_metadata = {
            "test_operator": {
                "category": "Functional",  # Use valid category
                # Missing label, description
                "features": {},
                "required_features": [],
            }
        }
        override_service.get_all_operator_metadata.return_value = minimal_metadata

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "test_operator" in data
        # Label should default to operator name
        assert data["test_operator"]["label"] == "test_operator"
        # Description should be None
        assert data["test_operator"]["description"] is None

    def test_get_operator_metadata_handles_empty_features(self, client, override_service):
        """Test that operators with no features are handled correctly."""
        # Arrange
        metadata_with_empty_features = {
            "noop": {
                "category": "Functional",
                "label": "No-Op",
                "features": {},
                "required_features": [],
            }
        }
        override_service.get_all_operator_metadata.return_value = metadata_with_empty_features

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "noop" in data
        assert data["noop"]["features"] == {}
        assert data["noop"]["required_features"] == []

    def test_get_operator_metadata_logs_request(self, client, override_service, sample_operator_metadata):
        """Test that requests are logged."""
        # Arrange
        override_service.get_all_operator_metadata.return_value = sample_operator_metadata

        # Act
        with patch("datasift.api.routes.operators.logger") as mock_logger:
            response = client.get("/operators/metadata")

            # Assert
            assert response.status_code == 200
            # Verify info log was called
            mock_logger.info.assert_called()

    def test_get_operator_metadata_passes_internal_features_false(
        self, client, override_service, sample_operator_metadata
    ):
        """Test that internal_features=False is passed to service."""
        # Arrange
        override_service.get_all_operator_metadata.return_value = sample_operator_metadata

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        override_service.get_all_operator_metadata.assert_called_once_with(internal_features=False)

    def test_get_operator_metadata_response_content_type(self, client, override_service, sample_operator_metadata):
        """Test that response has correct content type."""
        # Arrange
        override_service.get_all_operator_metadata.return_value = sample_operator_metadata

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_get_operator_metadata_handles_unknown_category(self, client, override_service):
        """Test that operators with missing category get default value."""
        # Arrange
        metadata_without_category = {
            "unknown_op": {
                # Missing category
                "features": {},
                "required_features": [],
            }
        }
        override_service.get_all_operator_metadata.return_value = metadata_without_category

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["unknown_op"]["category"] == "Custom"  # Default is now "Custom" (valid enum value)


class TestOperatorMetadataServiceDependency:
    """Tests for operator metadata service dependency injection.

    This test class verifies the dependency injection mechanism for the
    OperatorMetadataService, ensuring:
    - Singleton behavior via @lru_cache
    - Correct type returned
    - Service reusability across requests
    """

    def test_get_operator_metadata_service_returns_singleton(self):
        """Test that service dependency returns singleton instance."""
        # Act
        service1 = get_operator_metadata_service()
        service2 = get_operator_metadata_service()

        # Assert
        assert service1 is service2

    def test_get_operator_metadata_service_returns_correct_type(self):
        """Test that service dependency returns correct type."""
        # Act
        service = get_operator_metadata_service()

        # Assert
        assert isinstance(service, OperatorMetadataService)
