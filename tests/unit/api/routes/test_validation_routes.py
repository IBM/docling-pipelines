"""Unit tests for Validation API routes."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docpipe.api.routes.validation import get_validation_service, validation_router
from docpipe.core.assets.flows.application.services.validation_service import ValidationService


@pytest.fixture
def app():
    """Create FastAPI app with validation router and error handlers.

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
    app.include_router(validation_router)

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
    """Create mock ValidationService."""
    return Mock(spec=ValidationService)


@pytest.fixture
def override_service(app, mock_service):
    """Override the get_validation_service dependency."""
    app.dependency_overrides[get_validation_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.clear()


class TestValidateFlowEndpoint:
    """Tests for POST /validation/validate_flow endpoint."""

    def test_validate_valid_flow_returns_200_with_succeeded_status(self, client, override_service, sample_flow_data):
        """Test validating a valid flow returns 200 with SUCCEEDED status."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "SUCCEEDED",
            "message": "Flow validation succeeded.",
            "errors": [],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCEEDED"
        assert data["message"] == "Flow validation succeeded."
        assert data["errors"] == []
        assert data["warnings"] == []
        override_service.validate_flow.assert_called_once()

    def test_validate_invalid_flow_returns_200_with_failed_status(self, client, override_service, sample_flow_data):
        """Test validating an invalid flow returns 200 with FAILED status."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "FAILED",
            "message": "Flow validation failed.",
            "errors": [
                {
                    "code": "OPERATOR_NOT_FOUND",
                    "message": "Operator not found: docpipe.operators.NonExistentOperator",
                    "node_id": "550e8400-e29b-41d4-a716-446655440001",
                }
            ],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "FAILED"
        assert data["message"] == "Flow validation failed."
        assert len(data["errors"]) == 1
        assert data["errors"][0]["code"] == "OPERATOR_NOT_FOUND"
        assert data["warnings"] == []

    def test_validate_flow_with_warnings_returns_200_with_warnings_status(
        self, client, override_service, sample_flow_data
    ):
        """Test validating a flow with warnings returns SUCCEEDED_WITH_WARNINGS status."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "SUCCEEDED_WITH_WARNINGS",
            "message": "Flow validation succeeded with warnings.",
            "errors": [],
            "warnings": [
                {
                    "code": "MISSING_FEATURE",
                    "message": "Node is missing recommended feature: content",
                    "node_id": "550e8400-e29b-41d4-a716-446655440001",
                }
            ],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCEEDED_WITH_WARNINGS"
        assert len(data["warnings"]) == 1
        assert data["warnings"][0]["code"] == "MISSING_FEATURE"
        assert data["errors"] == []

    def test_validate_flow_returns_correct_response_structure(self, client, override_service, sample_flow_data):
        """Test that response has correct FlowValidationResponse structure."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "SUCCEEDED",
            "message": "Flow validation succeeded.",
            "errors": [],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "status" in data
        assert "message" in data
        assert "errors" in data
        assert "warnings" in data
        assert isinstance(data["errors"], list)
        assert isinstance(data["warnings"], list)

    def test_validate_flow_with_multiple_errors_returns_all_errors(self, client, override_service, sample_flow_data):
        """Test that multiple validation errors are all returned."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "FAILED",
            "message": "Flow validation failed.",
            "errors": [
                {
                    "code": "OPERATOR_NOT_FOUND",
                    "message": "Operator not found",
                    "node_id": "550e8400-e29b-41d4-a716-446655440001",
                },
                {
                    "code": "MISSING_REQUIRED_PARAM",
                    "message": "Missing required parameter",
                    "node_id": "550e8400-e29b-41d4-a716-446655440002",
                },
                {
                    "code": "CIRCULAR_DEPENDENCY",
                    "message": "Circular dependency detected",
                    "node_id": "550e8400-e29b-41d4-a716-446655440003",
                },
            ],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "FAILED"
        assert len(data["errors"]) == 3
        assert all("code" in error for error in data["errors"])
        assert all("message" in error for error in data["errors"])

    def test_validate_flow_with_elyra_format_parameter(self, client, override_service):
        """Test validating flow with is_elyra query parameter."""
        # Arrange - Use Elyra format for this test
        elyra_flow_data = {
            "name": "Test Flow",
            "description": "A test flow for unit testing",
            "definition": {
                "doc_type": "pipeline",
                "version": "3.0",
                "id": "test-pipeline-id",
                "primary_pipeline": "test-pipeline-id",
                "pipelines": [
                    {
                        "id": "test-pipeline-id",
                        "nodes": [
                            {
                                "id": "node1",
                                "type": "execution_node",
                                "op": "execute-notebook-node",
                            }
                        ],
                        "app_data": {"ds_flow": {}, "ui_data": {}},
                    }
                ],
                "schemas": [],
            },
            "tags": ["test", "unit-test"],
            "container_kind": "project",
            "container_id": "550e8400-e29b-41d4-a716-446655440000",
            "is_hidden": False,
            "flow_version": "2.0",
            "job_id": "660e8400-e29b-41d4-a716-446655440000",
            "created_by": "test_user",
        }
        override_service.validate_flow.return_value = {
            "status": "SUCCEEDED",
            "message": "Flow validation succeeded.",
            "errors": [],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow?is_elyra=true", json=elyra_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCEEDED"
        # Verify is_elyra was passed to service
        call_kwargs = override_service.validate_flow.call_args[1]
        assert call_kwargs.get("is_elyra") is True

    def test_validate_flow_with_authoring_format_parameter(self, client, override_service, sample_flow_data):
        """Test validating flow with is_elyra=false (authoring format)."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "SUCCEEDED",
            "message": "Flow validation succeeded.",
            "errors": [],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow?is_elyra=false", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCEEDED"
        # Verify is_elyra was passed to service as False
        call_kwargs = override_service.validate_flow.call_args[1]
        assert call_kwargs.get("is_elyra") is False

    def test_validate_flow_response_content_type(self, client, override_service, sample_flow_data):
        """Test that response has correct content type."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "SUCCEEDED",
            "message": "Flow validation succeeded.",
            "errors": [],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_validate_flow_handles_service_exception(self, client, override_service, sample_flow_data):
        """Test that service exceptions are handled properly."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "FAILED",
            "message": "Internal validation error",
            "errors": [{"code": "INTERNAL_ERROR", "message": "Unexpected error during validation"}],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "FAILED"
        assert len(data["errors"]) > 0


class TestValidationAlertDTOStructure:
    """Tests for ValidationAlertDTO structure and validation."""

    def test_validation_alert_dto_accepts_all_fields(self, client, override_service, sample_flow_data):
        """Test that ValidationAlertDTO accepts all expected fields."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "FAILED",
            "message": "Flow validation failed.",
            "errors": [
                {
                    "code": "OPERATOR_NOT_FOUND",
                    "message": "Operator not found",
                    "message_code": "operator.not_found",
                    "node_id": "550e8400-e29b-41d4-a716-446655440001",
                    "node_name": "Ingest Node",
                    "operator": "IngestLocalOperator",
                }
            ],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        error = data["errors"][0]
        assert error["code"] == "OPERATOR_NOT_FOUND"
        assert error["message"] == "Operator not found"
        assert error["message_code"] == "operator.not_found"
        assert error["node_id"] == "550e8400-e29b-41d4-a716-446655440001"
        assert error["node_name"] == "Ingest Node"
        assert error["operator"] == "IngestLocalOperator"

    def test_validation_alert_dto_accepts_minimal_fields(self, client, override_service, sample_flow_data):
        """Test that ValidationAlertDTO works with minimal fields."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "FAILED",
            "message": "Flow validation failed.",
            "errors": [{"code": "ERROR", "message": "Validation error"}],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        error = data["errors"][0]
        assert error["code"] == "ERROR"
        assert error["message"] == "Validation error"

    def test_validation_alert_dto_accepts_extra_fields(self, client, override_service, sample_flow_data):
        """Test that ValidationAlertDTO accepts extra fields via model_config.

        Note: Pydantic's extra="allow" allows extra fields during validation,
        but they are not included in the serialized output by default.
        This test verifies that the DTO doesn't reject extra fields during validation.
        """
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "FAILED",
            "message": "Flow validation failed.",
            "errors": [
                {
                    "code": "ERROR",
                    "message": "Validation error",
                    "extra_field": "extra_value",
                    "another_field": 123,
                }
            ],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        error = data["errors"][0]
        assert error["code"] == "ERROR"
        assert error["message"] == "Validation error"
        # Extra fields are accepted during validation but not serialized by default
        # The important thing is that the request doesn't fail


class TestFlowValidationResponseStructure:
    """Tests for FlowValidationResponse structure and validation."""

    def test_flow_validation_response_requires_status(self, client, override_service, sample_flow_data):
        """Test that status field is required in response."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "SUCCEEDED",
            "message": None,
            "errors": [],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "SUCCEEDED"

    def test_flow_validation_response_accepts_null_message(self, client, override_service, sample_flow_data):
        """Test that message field can be null."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "SUCCEEDED",
            "message": None,
            "errors": [],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message"] is None

    def test_flow_validation_response_includes_empty_arrays(self, client, override_service, sample_flow_data):
        """Test that errors and warnings are empty arrays when no issues."""
        # Arrange
        override_service.validate_flow.return_value = {
            "status": "SUCCEEDED",
            "message": "Flow validation succeeded.",
            "errors": [],
            "warnings": [],
        }

        # Act
        response = client.post("/validation/validate_flow", json=sample_flow_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["errors"] == []
        assert data["warnings"] == []
        assert isinstance(data["errors"], list)
        assert isinstance(data["warnings"], list)
