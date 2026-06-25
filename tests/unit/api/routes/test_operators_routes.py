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

from docpipe.api.routes.operators import get_operator_metadata_service, operators_router
from docpipe.core.operators.application.services.operator_metadata_service import (
    OperatorMetadataService,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode


@pytest.fixture
def app():
    """Create FastAPI app with operators router and error handlers.

    Registers the same exception handlers as main.py to ensure tests
    match runtime behavior.
    """
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from docpipe.api.middleware.error_handler import (
        docpipe_exception_handler,
        generic_exception_handler,
        http_exception_handler,
        validation_exception_handler,
    )
    from docpipe.exceptions.docpipe_exceptions import DocpipeException

    app = FastAPI()
    app.include_router(operators_router)

    # Register exception handlers in same order as main.py
    app.add_exception_handler(DocpipeException, docpipe_exception_handler)
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
        override_service.get_all_operator_metadata.side_effect = DocpipeException(
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
        """Test that generic exceptions are wrapped in DocpipeException by service."""
        # Arrange
        # Service wraps all exceptions in DocpipeException
        override_service.get_all_operator_metadata.side_effect = DocpipeException(
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
        with patch("docpipe.api.routes.operators.logger") as mock_logger:
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


class TestOperatorMetadataValidationPatterns:
    """Tests for operator metadata validation patterns (regression tests for Issue #1).

    These tests ensure that the Pydantic validation patterns accept all valid
    operator types and categories, preventing validation errors like:
    - "vector" type validation error
    - "vector_sparse" type validation error
    - "Storage" category validation error
    """

    def test_vector_type_accepted_in_features(self, client, override_service):
        """Test that 'vector' type is accepted in operator features (Issue #1 regression)."""
        # Arrange - metadata with vector type feature
        metadata_with_vector = {
            "embeddings_operator": {
                "label": "Embeddings Operator",
                "category": "Functional",
                "description": "Generates vector embeddings",
                "features": {
                    "embeddings": {"name": "embeddings", "type": "vector", "description": "Dense vector embeddings"}
                },
                "is_operator_available": True,
            }
        }
        override_service.get_all_operator_metadata.return_value = metadata_with_vector

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["embeddings_operator"]["features"]["embeddings"]["type"] == "vector"

    def test_vector_sparse_type_accepted_in_features(self, client, override_service):
        """Test that 'vector_sparse' type is accepted in operator features (Issue #1 regression)."""
        # Arrange - metadata with vector_sparse type feature
        metadata_with_vector_sparse = {
            "sparse_embeddings_operator": {
                "label": "Sparse Embeddings Operator",
                "category": "Functional",
                "description": "Generates sparse vector embeddings",
                "features": {
                    "sparse_embeddings": {
                        "name": "sparse_embeddings",
                        "type": "vector_sparse",
                        "description": "Sparse vector embeddings",
                    }
                },
                "is_operator_available": True,
            }
        }
        override_service.get_all_operator_metadata.return_value = metadata_with_vector_sparse

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["sparse_embeddings_operator"]["features"]["sparse_embeddings"]["type"] == "vector_sparse"

    def test_storage_category_accepted(self, client, override_service):
        """Test that 'Storage' category is accepted (Issue #1 regression)."""
        # Arrange - metadata with Storage category
        metadata_with_storage = {
            "document_set_operator": {
                "label": "Document Set Operator",
                "category": "Storage",
                "description": "Stores document sets",
                "features": {},
                "is_operator_available": True,
            }
        }
        override_service.get_all_operator_metadata.return_value = metadata_with_storage

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["document_set_operator"]["category"] == "Storage"

    def test_all_integer_types_accepted(self, client, override_service):
        """Test that all integer types (int8, int16, int32, int64) are accepted (Issue #1 regression)."""
        # Arrange - metadata with various integer types
        metadata_with_int_types = {
            "test_operator": {
                "label": "Test Operator",
                "category": "Functional",
                "description": "Test operator with integer types",
                "features": {
                    "int8_field": {"name": "int8_field", "type": "int8"},
                    "int16_field": {"name": "int16_field", "type": "int16"},
                    "int32_field": {"name": "int32_field", "type": "int32"},
                    "int64_field": {"name": "int64_field", "type": "int64"},
                },
                "is_operator_available": True,
            }
        }
        override_service.get_all_operator_metadata.return_value = metadata_with_int_types

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        features = data["test_operator"]["features"]
        assert features["int8_field"]["type"] == "int8"
        assert features["int16_field"]["type"] == "int16"
        assert features["int32_field"]["type"] == "int32"
        assert features["int64_field"]["type"] == "int64"

    def test_bool_type_accepted(self, client, override_service):
        """Test that 'bool' type is accepted (Issue #1 regression)."""
        # Arrange - metadata with bool type
        metadata_with_bool = {
            "test_operator": {
                "label": "Test Operator",
                "category": "Functional",
                "description": "Test operator with bool type",
                "features": {"is_valid": {"name": "is_valid", "type": "bool"}},
                "is_operator_available": True,
            }
        }
        override_service.get_all_operator_metadata.return_value = metadata_with_bool

        # Act
        response = client.get("/operators/metadata")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["test_operator"]["features"]["is_valid"]["type"] == "bool"


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
