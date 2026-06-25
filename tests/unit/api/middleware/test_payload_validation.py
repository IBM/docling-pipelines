"""
Unit tests for payload validation middleware.

Tests the validate_payload_size middleware function to ensure it correctly
validates request payload sizes and prevents excessive memory usage.
"""

import json
from unittest.mock import Mock

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from docpipe.api.middleware.payload_validation import (
    MAX_PAYLOAD_SIZE,
    validate_payload_size,
)


class TestPayloadValidationMiddleware:
    """Test suite for payload validation middleware"""

    @pytest.fixture
    def mock_call_next(self):
        """Create a mock call_next function that returns a successful response"""

        async def call_next(request):
            return JSONResponse(status_code=200, content={"status": "success"})

        return call_next

    @pytest.fixture
    def create_mock_request(self):
        """Factory fixture to create mock requests with different configurations"""

        def _create_request(method: str, content_length: int | None = None):
            request = Mock(spec=Request)
            request.method = method
            request.headers = Mock()
            if content_length is not None:
                request.headers.get = Mock(return_value=str(content_length))
            else:
                request.headers.get = Mock(return_value=None)
            return request

        return _create_request

    # Valid Requests Tests

    @pytest.mark.anyio
    async def test_small_payload_passes_through(self, create_mock_request, mock_call_next):
        """Test that small payloads (< 5MB) pass through successfully"""
        # Arrange
        small_payload_size = 1024 * 1024  # 1MB
        request = create_mock_request("POST", small_payload_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 200
        assert response.body == b'{"status":"success"}'

    @pytest.mark.anyio
    async def test_no_content_length_header_passes(self, create_mock_request, mock_call_next):
        """Test that requests without content-length header pass through"""
        # Arrange
        request = create_mock_request("POST", None)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_get_request_passes_without_validation(self, create_mock_request, mock_call_next):
        """Test that GET requests pass through without payload validation"""
        # Arrange
        request = create_mock_request("GET", None)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_get_request_with_large_content_length_passes(self, create_mock_request, mock_call_next):
        """Test that GET requests pass even with large content-length header"""
        # Arrange
        large_size = MAX_PAYLOAD_SIZE + 1000
        request = create_mock_request("GET", large_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 200

    # Invalid Requests Tests

    @pytest.mark.anyio
    async def test_large_payload_returns_413(self, create_mock_request, mock_call_next):
        """Test that payloads > 5MB return 413 status code"""
        # Arrange
        large_payload_size = MAX_PAYLOAD_SIZE + 1024  # Just over 5MB
        request = create_mock_request("POST", large_payload_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 413

    @pytest.mark.anyio
    async def test_error_message_format(self, create_mock_request, mock_call_next):
        """Test that error response has correct message format"""
        # Arrange
        large_payload_size = MAX_PAYLOAD_SIZE + 1024
        request = create_mock_request("POST", large_payload_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 413
        # Parse response body
        body_bytes = response.body if isinstance(response.body, bytes) else bytes(response.body)
        body = json.loads(body_bytes.decode())
        assert "detail" in body
        assert "Payload too large" in body["detail"]
        assert "5.0MB" in body["detail"]

    @pytest.mark.anyio
    async def test_error_response_content_type(self, create_mock_request, mock_call_next):
        """Test that error response has correct content type"""
        # Arrange
        large_payload_size = MAX_PAYLOAD_SIZE + 1024
        request = create_mock_request("POST", large_payload_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 413
        assert response.media_type == "application/json"

    # Edge Cases Tests

    @pytest.mark.anyio
    async def test_exactly_5mb_payload_passes(self, create_mock_request, mock_call_next):
        """Test that exactly 5MB payload passes through"""
        # Arrange
        exact_size = MAX_PAYLOAD_SIZE
        request = create_mock_request("POST", exact_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_just_over_5mb_fails(self, create_mock_request, mock_call_next):
        """Test that payload just over 5MB fails validation"""
        # Arrange
        just_over_size = MAX_PAYLOAD_SIZE + 1
        request = create_mock_request("POST", just_over_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 413

    @pytest.mark.anyio
    async def test_missing_content_length_on_post_passes(self, create_mock_request, mock_call_next):
        """Test that POST without content-length header passes (no validation)"""
        # Arrange
        request = create_mock_request("POST", None)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 200

    # Method-Specific Tests

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "method",
        ["POST", "PUT", "PATCH"],
    )
    async def test_validation_applies_to_write_methods(self, method, create_mock_request, mock_call_next):
        """Test that validation applies to POST, PUT, and PATCH methods"""
        # Arrange
        large_size = MAX_PAYLOAD_SIZE + 1024
        request = create_mock_request(method, large_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 413

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "method",
        ["GET", "DELETE", "HEAD", "OPTIONS"],
    )
    async def test_validation_skipped_for_read_methods(self, method, create_mock_request, mock_call_next):
        """Test that validation is skipped for GET, DELETE, HEAD, OPTIONS"""
        # Arrange
        large_size = MAX_PAYLOAD_SIZE + 1024
        request = create_mock_request(method, large_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 200

    # Payload Size Boundary Tests

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "payload_size,should_pass",
        [
            (0, True),  # Empty payload
            (1024, True),  # 1KB
            (1024 * 1024, True),  # 1MB
            (MAX_PAYLOAD_SIZE - 1, True),  # Just under limit
            (MAX_PAYLOAD_SIZE, True),  # Exactly at limit
            (MAX_PAYLOAD_SIZE + 1, False),  # Just over limit
            (MAX_PAYLOAD_SIZE * 2, False),  # 10MB
            (MAX_PAYLOAD_SIZE * 10, False),  # 50MB
        ],
    )
    async def test_payload_size_boundaries(self, payload_size, should_pass, create_mock_request, mock_call_next):
        """Test various payload sizes around the 5MB boundary"""
        # Arrange
        request = create_mock_request("POST", payload_size)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        if should_pass:
            assert response.status_code == 200
        else:
            assert response.status_code == 413

    # Integration-Style Tests

    @pytest.mark.anyio
    async def test_middleware_does_not_modify_valid_request(self, create_mock_request):
        """Test that middleware doesn't modify valid requests"""
        # Arrange
        request = create_mock_request("POST", 1024)
        original_method = request.method

        async def call_next(req):
            # Verify request is unchanged
            assert req.method == original_method
            return JSONResponse(status_code=200, content={"data": "test"})

        # Act
        response = await validate_payload_size(request, call_next)

        # Assert
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_middleware_short_circuits_on_large_payload(self, create_mock_request):
        """Test that middleware doesn't call next handler for large payloads"""
        # Arrange
        large_size = MAX_PAYLOAD_SIZE + 1024
        request = create_mock_request("POST", large_size)
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return JSONResponse(status_code=200, content={})

        # Act
        response = await validate_payload_size(request, call_next)

        # Assert
        assert response.status_code == 413
        assert not call_next_called, "call_next should not be invoked for large payloads"

    @pytest.mark.anyio
    async def test_zero_content_length_passes(self, create_mock_request, mock_call_next):
        """Test that zero content-length passes validation"""
        # Arrange
        request = create_mock_request("POST", 0)

        # Act
        response = await validate_payload_size(request, mock_call_next)

        # Assert
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_max_payload_size_constant_value(self):
        """Test that MAX_PAYLOAD_SIZE constant has expected value"""
        # Assert
        assert MAX_PAYLOAD_SIZE == 5 * 1024 * 1024
        assert MAX_PAYLOAD_SIZE == 5242880  # 5MB in bytes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
