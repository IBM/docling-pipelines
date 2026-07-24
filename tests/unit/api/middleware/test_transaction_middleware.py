"""Tests for transaction middleware."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from starlette.responses import Response

from docpipe.api.middleware.transaction_middleware import TransactionMiddleware


@pytest.fixture
def mock_request():
    """Create a mock request."""
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.headers = {}
    return request


@pytest.fixture
def mock_call_next():
    """Create a mock call_next function."""

    async def call_next(request):
        response = Response(content="test", status_code=200)
        return response

    return call_next


@pytest.mark.anyio
async def test_transaction_middleware_generates_id_when_not_provided(mock_request, mock_call_next):
    """Test that middleware generates transaction ID when not provided in header."""
    middleware = TransactionMiddleware(app=MagicMock())

    response = await middleware.dispatch(mock_request, mock_call_next)

    # Verify transaction ID was set in request state
    assert hasattr(mock_request.state, "transaction_id")
    transaction_id = mock_request.state.transaction_id

    # Verify it's a valid UUID
    uuid.UUID(transaction_id)

    # Verify transaction ID was added to response headers
    assert "X-Transaction-ID" in response.headers
    assert response.headers["X-Transaction-ID"] == transaction_id


@pytest.mark.anyio
async def test_transaction_middleware_uses_global_transaction_id(mock_request, mock_call_next):
    """Test that middleware uses X-Global-Transaction-Id from request header."""
    provided_id = "test-transaction-123"
    mock_request.headers = {"X-Global-Transaction-Id": provided_id}

    middleware = TransactionMiddleware(app=MagicMock())

    response = await middleware.dispatch(mock_request, mock_call_next)

    # Verify provided transaction ID was used
    assert mock_request.state.transaction_id == provided_id

    # Verify same ID was added to response headers as X-Transaction-ID
    assert response.headers["X-Transaction-ID"] == provided_id


@pytest.mark.anyio
async def test_transaction_middleware_preserves_response_content(mock_request, mock_call_next):
    """Test that middleware preserves response content and status."""
    middleware = TransactionMiddleware(app=MagicMock())

    response = await middleware.dispatch(mock_request, mock_call_next)

    # Verify response content and status are preserved
    assert response.status_code == 200
    assert response.body == b"test"


@pytest.mark.anyio
async def test_transaction_middleware_handles_empty_header(mock_request, mock_call_next):
    """Test that middleware handles empty X-Global-Transaction-Id header."""
    mock_request.headers = {"X-Global-Transaction-Id": ""}

    middleware = TransactionMiddleware(app=MagicMock())

    await middleware.dispatch(mock_request, mock_call_next)

    # Verify new transaction ID was generated (empty string is falsy)
    assert mock_request.state.transaction_id
    assert mock_request.state.transaction_id != ""

    # Verify it's a valid UUID
    uuid.UUID(mock_request.state.transaction_id)


@pytest.mark.anyio
async def test_transaction_middleware_unique_ids_per_request(mock_call_next):
    """Test that each request gets a unique transaction ID."""
    middleware = TransactionMiddleware(app=MagicMock())

    # Create two separate requests
    request1 = MagicMock(spec=Request)
    request1.state = MagicMock()
    request1.headers = {}

    request2 = MagicMock(spec=Request)
    request2.state = MagicMock()
    request2.headers = {}

    # Process both requests
    response1 = await middleware.dispatch(request1, mock_call_next)
    response2 = await middleware.dispatch(request2, mock_call_next)

    # Verify each request got a unique transaction ID
    id1 = request1.state.transaction_id
    id2 = request2.state.transaction_id

    assert id1 != id2
    assert response1.headers["X-Transaction-ID"] == id1
    assert response2.headers["X-Transaction-ID"] == id2


@pytest.mark.anyio
async def test_transaction_middleware_response_header_format(mock_request, mock_call_next):
    """Test that middleware returns transaction ID in X-Transaction-ID response header."""
    global_id = "global-trace-456"
    mock_request.headers = {"X-Global-Transaction-Id": global_id}

    middleware = TransactionMiddleware(app=MagicMock())

    response = await middleware.dispatch(mock_request, mock_call_next)

    # Verify global transaction ID was used
    assert mock_request.state.transaction_id == global_id

    # Verify response uses X-Transaction-ID header (not X-Global-Transaction-Id)
    assert response.headers["X-Transaction-ID"] == global_id
    assert "X-Global-Transaction-Id" not in response.headers


@pytest.mark.anyio
async def test_transaction_middleware_generated_id_in_response(mock_request, mock_call_next):
    """Test that generated transaction ID is returned in X-Transaction-ID response header."""
    middleware = TransactionMiddleware(app=MagicMock())

    response = await middleware.dispatch(mock_request, mock_call_next)

    # Verify transaction ID was generated
    transaction_id = mock_request.state.transaction_id
    uuid.UUID(transaction_id)  # Verify it's a valid UUID

    # Verify response uses X-Transaction-ID header
    assert response.headers["X-Transaction-ID"] == transaction_id
    assert "X-Global-Transaction-Id" not in response.headers
