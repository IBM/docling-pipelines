"""Unit tests for ApiLoggingMiddleware."""

import logging
from unittest.mock import MagicMock

import pytest
from starlette.responses import Response

from docpipe.api.middleware.api_logging_middleware import ApiLoggingMiddleware

# The middleware uses logging.getLogger(__name__), which gives this logger name.
_MIDDLEWARE_LOGGER = "docpipe.api.middleware.api_logging_middleware"


@pytest.fixture(autouse=True)
def _capture_middleware_logs(caplog):
    """Attach caplog handler directly — docpipe logger has propagate=False."""
    middleware_logger = logging.getLogger(_MIDDLEWARE_LOGGER)
    middleware_logger.addHandler(caplog.handler)
    middleware_logger.setLevel(logging.DEBUG)
    yield
    middleware_logger.removeHandler(caplog.handler)


@pytest.fixture
def mock_request():
    """Create a mock request for a non-health-check endpoint."""
    request = MagicMock()
    request.url.path = "/api/v1/flows"
    request.method = "GET"
    return request


@pytest.fixture
def mock_call_next():
    """Create a mock call_next that returns a 200 response."""

    async def call_next(request):
        return Response(content="ok", status_code=200)

    return call_next


class TestApiLoggingMiddlewareRequestLogging:
    """Tests for request and response logging behaviour."""

    @pytest.mark.anyio
    async def test_request_is_logged(self, mock_request, mock_call_next, caplog):
        """Incoming request method and path should be logged."""
        middleware = ApiLoggingMiddleware(app=MagicMock())

        await middleware.dispatch(mock_request, mock_call_next)

        assert any("Request: GET /api/v1/flows" in msg for msg in caplog.messages)

    @pytest.mark.anyio
    async def test_response_is_logged_with_status_and_duration(self, mock_request, mock_call_next, caplog):
        """Response log should include status code, method, path, and duration."""
        middleware = ApiLoggingMiddleware(app=MagicMock())

        await middleware.dispatch(mock_request, mock_call_next)

        response_logs = [msg for msg in caplog.messages if msg.startswith("Response:")]
        assert len(response_logs) == 1
        log_line = response_logs[0]
        assert "200" in log_line
        assert "GET" in log_line
        assert "/api/v1/flows" in log_line
        assert "Duration:" in log_line
        assert "ms" in log_line

    @pytest.mark.anyio
    async def test_duration_is_non_negative(self, mock_request, mock_call_next, caplog):
        """Duration reported in the log must be >= 0."""
        middleware = ApiLoggingMiddleware(app=MagicMock())

        await middleware.dispatch(mock_request, mock_call_next)

        response_logs = [msg for msg in caplog.messages if msg.startswith("Response:")]
        # Extract duration value from "Duration: 0.12ms"
        log_line = response_logs[0]
        duration_str = log_line.split("Duration: ")[1].rstrip("]").replace("ms", "")
        assert float(duration_str) >= 0


class TestApiLoggingMiddlewareHealthCheckFiltering:
    """Tests for health check endpoint filtering."""

    @pytest.mark.anyio
    async def test_health_path_is_not_logged(self, mock_call_next, caplog):
        """Requests to /health should not produce any log output."""
        request = MagicMock()
        request.url.path = "/health"
        request.method = "GET"

        middleware = ApiLoggingMiddleware(app=MagicMock())

        await middleware.dispatch(request, mock_call_next)

        assert len(caplog.messages) == 0

    @pytest.mark.anyio
    async def test_root_path_is_not_logged(self, mock_call_next, caplog):
        """Requests to / should not produce any log output."""
        request = MagicMock()
        request.url.path = "/"
        request.method = "GET"

        middleware = ApiLoggingMiddleware(app=MagicMock())

        await middleware.dispatch(request, mock_call_next)

        assert len(caplog.messages) == 0

    @pytest.mark.anyio
    async def test_non_health_endpoint_is_logged(self, mock_call_next, caplog):
        """Non-health endpoints should be logged normally."""
        request = MagicMock()
        request.url.path = "/api/v1/operators"
        request.method = "POST"

        middleware = ApiLoggingMiddleware(app=MagicMock())

        await middleware.dispatch(request, mock_call_next)

        assert any("Request: POST /api/v1/operators" in msg for msg in caplog.messages)


class TestApiLoggingMiddlewareResponsePreservation:
    """Tests that the middleware does not alter the response."""

    @pytest.mark.anyio
    async def test_response_status_code_preserved(self, mock_request):
        """Middleware must not alter the response status code."""

        async def call_next(request):
            return Response(content="created", status_code=201)

        middleware = ApiLoggingMiddleware(app=MagicMock())

        response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 201

    @pytest.mark.anyio
    async def test_response_body_preserved(self, mock_request, mock_call_next):
        """Middleware must not alter the response body."""
        middleware = ApiLoggingMiddleware(app=MagicMock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.body == b"ok"

    @pytest.mark.anyio
    async def test_health_check_response_passed_through(self):
        """Health check response must be returned unmodified."""
        request = MagicMock()
        request.url.path = "/health"
        request.method = "GET"

        async def call_next(request):
            return Response(content="healthy", status_code=200)

        middleware = ApiLoggingMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        assert response.body == b"healthy"
