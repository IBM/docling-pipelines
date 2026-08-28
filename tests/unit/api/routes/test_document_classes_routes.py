"""Unit tests for Document Classes API routes.

Covers:
- 200 with list of document classes on success
- 200 with empty list when no classes available
- 500 when DocumentClassUtils raises unexpectedly
- Response structure matches DocumentClassItem schema
- Dependency injection and singleton behaviour
- DocumentClassService delegates to DocumentClassUtils.get_document_types()
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from docpipe.api.routes.document_classes import (
    DocumentClassService,
    document_classes_router,
    get_document_class_service,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode


@pytest.fixture
def app():
    """FastAPI app with the document_classes router and standard error handlers."""
    from docpipe.api.middleware.error_handler import (
        docpipe_exception_handler,
        generic_exception_handler,
        http_exception_handler,
        validation_exception_handler,
    )

    test_app = FastAPI()
    test_app.include_router(document_classes_router)

    test_app.add_exception_handler(DocpipeException, docpipe_exception_handler)
    test_app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    test_app.add_exception_handler(RequestValidationError, validation_exception_handler)
    test_app.add_exception_handler(Exception, generic_exception_handler)

    return test_app


@pytest.fixture
def client(app):
    """TestClient for the test app."""
    return TestClient(app)


@pytest.fixture
def mock_service():
    """Mock DocumentClassService."""
    return Mock(spec=DocumentClassService)


@pytest.fixture
def override_service(app, mock_service):
    """Inject mock service into the app's dependency container."""
    app.dependency_overrides[get_document_class_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.clear()


@pytest.fixture
def sample_document_classes():
    """Sample document class data matching the service return format."""
    return [
        {"document_type": "Invoice", "document_description": "An invoice document"},
        {"document_type": "Passport", "document_description": "A passport document"},
    ]


class TestGetAllDocumentClassesEndpoint:
    """Tests for GET /document_classes."""

    def test_returns_200_with_valid_data(
        self, client: TestClient, override_service: Mock, sample_document_classes: list
    ) -> None:
        """Endpoint returns 200 when service returns data."""
        override_service.get_all_document_classes.return_value = sample_document_classes

        response = client.get("/document_classes")

        assert response.status_code == 200

    def test_returns_list_of_document_class_items(
        self, client: TestClient, override_service: Mock, sample_document_classes: list
    ) -> None:
        """Response body is a list with the expected document_type values."""
        override_service.get_all_document_classes.return_value = sample_document_classes

        response = client.get("/document_classes")
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2
        types = {item["document_type"] for item in data}
        assert types == {"Invoice", "Passport"}

    def test_response_items_contain_required_fields(
        self, client: TestClient, override_service: Mock, sample_document_classes: list
    ) -> None:
        """Each item in the response has document_type and document_description."""
        override_service.get_all_document_classes.return_value = sample_document_classes

        response = client.get("/document_classes")
        data = response.json()

        for item in data:
            assert "document_type" in item
            assert "document_description" in item

    def test_returns_empty_list_when_no_classes(self, client: TestClient, override_service: Mock) -> None:
        """Endpoint returns an empty list when the service returns no classes."""
        override_service.get_all_document_classes.return_value = []

        response = client.get("/document_classes")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_500_when_service_raises_docpipe_exception(
        self, client: TestClient, override_service: Mock
    ) -> None:
        """DocpipeException raised by service results in HTTP 500."""
        override_service.get_all_document_classes.side_effect = DocpipeException(
            message="Failed to retrieve document classes",
            status_code=500,
            error_code=ErrorCode.DOCUMENT_CLASS_LIST_FAILED,
        )

        response = client.get("/document_classes")

        assert response.status_code == 500

    def test_response_content_type_is_json(
        self, client: TestClient, override_service: Mock, sample_document_classes: list
    ) -> None:
        """Response Content-Type is application/json."""
        override_service.get_all_document_classes.return_value = sample_document_classes

        response = client.get("/document_classes")

        assert "application/json" in response.headers["content-type"]

    def test_description_value_is_preserved(self, client: TestClient, override_service: Mock) -> None:
        """document_description value is passed through unchanged."""
        description = "An invoice is a financial document issued by a seller."
        override_service.get_all_document_classes.return_value = [
            {"document_type": "Invoice", "document_description": description}
        ]

        response = client.get("/document_classes")
        data = response.json()

        assert data[0]["document_description"] == description


class TestDocumentClassServiceDelegation:
    """Tests for DocumentClassService delegating to DocumentClassUtils."""

    def test_delegates_to_document_class_utils(self) -> None:
        """get_all_document_classes() calls DocumentClassUtils.get_document_types()."""
        mock_result = {"Invoice": "An invoice", "Passport": "A passport"}

        with patch(
            "docpipe.api.routes.document_classes.DocumentClassUtils.get_document_types",
            return_value=mock_result,
        ):
            service = DocumentClassService()
            result = service.get_all_document_classes()

        assert len(result) == 2
        types = {item["document_type"] for item in result}
        assert types == {"Invoice", "Passport"}

    def test_converts_dict_to_list_format(self) -> None:
        """Result is converted from {type: desc} dict to list of dicts."""
        mock_result = {"Receipt": "A receipt document"}

        with patch(
            "docpipe.api.routes.document_classes.DocumentClassUtils.get_document_types",
            return_value=mock_result,
        ):
            service = DocumentClassService()
            result = service.get_all_document_classes()

        assert result == [{"document_type": "Receipt", "document_description": "A receipt document"}]

    def test_empty_utils_result_returns_empty_list(self) -> None:
        """Empty result from DocumentClassUtils returns an empty list."""
        with patch(
            "docpipe.api.routes.document_classes.DocumentClassUtils.get_document_types",
            return_value={},
        ):
            service = DocumentClassService()
            result = service.get_all_document_classes()

        assert result == []

    def test_raises_docpipe_exception_on_utils_error(self) -> None:
        """Unexpected error from DocumentClassUtils is wrapped in DocpipeException."""
        with patch(
            "docpipe.api.routes.document_classes.DocumentClassUtils.get_document_types",
            side_effect=RuntimeError("unexpected"),
        ):
            service = DocumentClassService()
            with pytest.raises(DocpipeException) as exc_info:
                service.get_all_document_classes()

        assert exc_info.value.status_code == 500
        assert "document_class_list_failed" in str(exc_info.value.error_code)


class TestDocumentClassServiceDependency:
    """Tests for the get_document_class_service dependency provider."""

    def test_returns_document_class_service_instance(self) -> None:
        """get_document_class_service() returns a DocumentClassService."""
        get_document_class_service.cache_clear()
        service = get_document_class_service()
        assert isinstance(service, DocumentClassService)

    def test_returns_same_instance_on_repeated_calls(self) -> None:
        """get_document_class_service() is cached — same object every call."""
        get_document_class_service.cache_clear()
        s1 = get_document_class_service()
        s2 = get_document_class_service()
        assert s1 is s2
