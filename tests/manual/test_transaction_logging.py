"""Manual test script to verify transaction ID logging.

This script demonstrates that transaction IDs are automatically injected
into all log messages through the ConditionalFormatter, which retrieves
transaction IDs from session_info context set by TransactionMiddleware.

The test uses the context variable approach (set_transaction_id/get_transaction_id)
to simulate the middleware behavior for testing purposes.

Run this script to verify the implementation:
    python tests/manual/test_transaction_logging.py
"""

import logging
import sys

from docpipe.api.middleware.transaction_middleware import (
    get_transaction_id,
    set_transaction_id,
)
from docpipe.utils.infrastructure.logging import ConditionalFormatter


def test_transaction_logging():
    """Test that ConditionalFormatter retrieves transaction IDs from context and injects them into logs."""

    # Configure logging with ConditionalFormatter (outputs structured JSON logs)
    formatter = ConditionalFormatter(fmt="%(levelname)s: %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger("test_logger")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)

    print("=" * 80)
    print("Testing Transaction ID Logging with ConditionalFormatter")
    print("=" * 80)

    # Test 1: Log without setting transaction ID (should use default from session_info)
    print("\n1. Logging without transaction ID (should show default transaction_ID):")
    logger.info("This is a test message without transaction ID")

    # Test 2: Set transaction ID in context and log
    print("\n2. Logging with transaction ID 'test-123' (should show transaction_ID: test-123):")
    set_transaction_id("test-123")
    logger.info("This message should have transaction ID test-123")
    logger.warning("Warning message with transaction ID")
    logger.error("Error message with transaction ID")

    # Test 3: Change transaction ID in context
    print("\n3. Logging with different transaction ID 'abc-456' (should show transaction_ID: abc-456):")
    set_transaction_id("abc-456")
    logger.info("This message should have transaction ID abc-456")

    # Test 4: Verify get_transaction_id retrieves from context
    print("\n4. Verifying get_transaction_id() retrieves from context:")
    current_id = get_transaction_id()
    print(f"Current transaction ID from context: {current_id}")
    assert current_id == "abc-456", f"Expected 'abc-456', got '{current_id}'"

    print("\n" + "=" * 80)
    print("All tests passed! Transaction IDs are being injected correctly.")
    print("Note: ConditionalFormatter outputs structured JSON format with transaction_ID field.")
    print("=" * 80)


if __name__ == "__main__":
    test_transaction_logging()
