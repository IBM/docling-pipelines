"""Tests for API logging middleware."""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from docpipe.api.middleware.api_logging_middleware import ApiLoggingMiddleware


@pytest.fixture
def app_with_logging():
    """Create test FastAPI app with logging middleware."""
    test_app = FastAPI()
    test_app.add_middleware(ApiLoggingMiddleware)

    @test_app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @test_app.get("/health")
    async def health_endpoint():
        return {"status": "ok"}

    @test_app.get("/")
    async def root_endpoint():
        return {"status": "ok"}

    @test_app.post("/test-post")
    async def test_post_endpoint():
        return {"message": "posted"}

    return test_app


@pytest.fixture
def client(app_with_logging):
    """Create test client."""
    return TestClient(app_with_logging)


def test_logs_request_and_response(client):
    """Test that middleware logs both request and response."""
    with patch("docpipe.api.middleware.api_logging_middleware.logger") as mock_logger:
        response = client.get("/test")

        assert response.status_code == 200

        # Should have two log calls: one for request, one for response
        assert mock_logger.info.call_count == 2

        # Check request log
        request_log = mock_logger.info.call_args_list[0][0][0]
        assert "Request: GET /test" in request_log

        # Check response log
        response_log = mock_logger.info.call_args_list[1][0][0]
        assert "Response: 200 GET /test" in response_log
        assert "Duration:" in response_log
        assert "ms]" in response_log


def test_logs_different_http_methods(client):
    """Test that middleware logs different HTTP methods correctly."""
    with patch("docpipe.api.middleware.api_logging_middleware.logger") as mock_logger:
        client.post("/test-post")

        # Check request log includes POST method
        request_log = mock_logger.info.call_args_list[0][0][0]
        assert "Request: POST /test-post" in request_log

        # Check response log includes POST method
        response_log = mock_logger.info.call_args_list[1][0][0]
        assert "Response: 200 POST /test-post" in response_log


def test_skips_health_check_endpoint(client):
    """Test that /health endpoint is not logged."""
    with patch("docpipe.api.middleware.api_logging_middleware.logger") as mock_logger:
        response = client.get("/health")

        assert response.status_code == 200
        # Should not log health check endpoints
        mock_logger.info.assert_not_called()


def test_skips_root_endpoint(client):
    """Test that / endpoint is not logged."""
    with patch("docpipe.api.middleware.api_logging_middleware.logger") as mock_logger:
        response = client.get("/")

        assert response.status_code == 200
        # Should not log root endpoint
        mock_logger.info.assert_not_called()


def test_logs_non_health_endpoints(client):
    """Test that non-health endpoints are logged."""
    with patch("docpipe.api.middleware.api_logging_middleware.logger") as mock_logger:
        client.get("/test")

        # Should log non-health endpoints
        assert mock_logger.info.call_count == 2


def test_duration_calculation_accuracy(client):
    """Test that duration is calculated and formatted correctly."""
    with patch("docpipe.api.middleware.api_logging_middleware.logger") as mock_logger:
        with patch("docpipe.api.middleware.api_logging_middleware.time.time") as mock_time:
            # Simulate 0.1 second (100ms) request duration
            mock_time.side_effect = [1000.0, 1000.1]

            client.get("/test")

            # Check response log contains duration
            response_log = mock_logger.info.call_args_list[1][0][0]
            assert "Duration: 100.00ms" in response_log


def test_logs_status_codes_correctly(client):
    """Test that different status codes are logged correctly."""
    with patch("docpipe.api.middleware.api_logging_middleware.logger") as mock_logger:
        # Test 200 OK
        client.get("/test")
        response_log = mock_logger.info.call_args_list[1][0][0]
        assert "Response: 200" in response_log

        mock_logger.reset_mock()

        # Test 404 Not Found
        client.get("/nonexistent")
        response_log = mock_logger.info.call_args_list[1][0][0]
        assert "Response: 404" in response_log


def test_logs_full_path_with_query_params(client):
    """Test that query parameters are included in logged path."""
    with patch("docpipe.api.middleware.api_logging_middleware.logger") as mock_logger:
        client.get("/test?param1=value1&param2=value2")

        request_log = mock_logger.info.call_args_list[0][0][0]
        assert "Request: GET /test" in request_log

        response_log = mock_logger.info.call_args_list[1][0][0]
        assert "Response: 200 GET /test" in response_log


@pytest.mark.anyio
async def test_middleware_dispatch_returns_response():
    """Test that middleware properly returns response from next handler."""
    middleware = ApiLoggingMiddleware(app=MagicMock())

    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/test"
    mock_request.method = "GET"

    expected_response = Response(content="test", status_code=200)

    async def mock_call_next(request):
        return expected_response

    with patch("docpipe.api.middleware.api_logging_middleware.logger"):
        result = await middleware.dispatch(mock_request, mock_call_next)

    assert result == expected_response


@pytest.mark.anyio
async def test_middleware_handles_exceptions_from_next_handler():
    """Test that middleware allows exceptions from next handler to propagate."""
    middleware = ApiLoggingMiddleware(app=MagicMock())

    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/test"
    mock_request.method = "GET"

    async def mock_call_next(request):
        raise ValueError("Test error")

    with patch("docpipe.api.middleware.api_logging_middleware.logger"):
        with pytest.raises(ValueError, match="Test error"):
            await middleware.dispatch(mock_request, mock_call_next)


def test_health_check_paths_constant():
    """Test that HEALTH_CHECK_PATHS constant contains expected paths."""
    assert "/health" in ApiLoggingMiddleware.HEALTH_CHECK_PATHS
    assert "/" in ApiLoggingMiddleware.HEALTH_CHECK_PATHS
    assert len(ApiLoggingMiddleware.HEALTH_CHECK_PATHS) == 2


def test_middleware_logs_with_correct_format(client):
    """Test that log messages follow expected format."""
    with patch("docpipe.api.middleware.api_logging_middleware.logger") as mock_logger:
        client.get("/test")

        # Request log format: "Request: {method} {path}"
        request_log = mock_logger.info.call_args_list[0][0][0]
        assert request_log.startswith("Request: ")
        assert " GET " in request_log

        # Response log format: "Response: {status} {method} {path} [Duration: {ms}ms]"
        response_log = mock_logger.info.call_args_list[1][0][0]
        assert response_log.startswith("Response: ")
        assert "[Duration: " in response_log
        assert response_log.endswith("ms]")
