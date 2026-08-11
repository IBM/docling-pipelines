"""
Unit test template for a docpipe operator.

Copy this file to tests/unit/operators/<category>/<operator_name>/test_<operator_name>.py
and replace MyOperator / my_operator with the real operator class and short_name.

See docs/guides/TESTING_STANDARDS.md and docs/guides/OPERATOR_TESTING_GUIDE.md for full guidance.
"""

import pyarrow as pa
import pytest

# Replace with the real operator import:
# from docpipe.core.operators.<category>.<module> import MyOperator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_config() -> dict:
    """Minimal valid configuration for the operator under test."""
    return {
        "doc_column": "content",
        # Add any required operator-specific config keys here
    }


@pytest.fixture
def sample_table() -> pa.Table:
    """Single-row table suitable for a happy-path test."""
    return pa.table(
        {
            "id": ["doc-1"],
            "name": ["sample.pdf"],
            "content": ["This is sample document content for testing."],
            "path": ["/tmp/sample.pdf"],
        }
    )


@pytest.fixture
def empty_table() -> pa.Table:
    """Zero-row table with correct schema."""
    return pa.table(
        {
            "id": pa.array([], type=pa.string()),
            "name": pa.array([], type=pa.string()),
            "content": pa.array([], type=pa.string()),
            "path": pa.array([], type=pa.string()),
        }
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestMyOperatorTransform:
    def test_returns_table_and_metadata_for_valid_input(self, valid_config: dict, sample_table: pa.Table) -> None:
        # op = MyOperator(config=valid_config)
        # tables, metadata = op.transform(sample_table)
        # assert len(tables) == 1
        # assert metadata["total_docs"] == 1
        pass  # replace with real assertions

    def test_returns_empty_table_without_error_for_empty_input(self, valid_config: dict, empty_table: pa.Table) -> None:
        # op = MyOperator(config=valid_config)
        # tables, metadata = op.transform(empty_table)
        # assert len(tables) == 1
        # assert tables[0].num_rows == 0
        pass  # replace with real assertions


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestMyOperatorEdgeCases:
    def test_skips_row_when_content_column_is_missing(self, valid_config: dict) -> None:
        # table_without_content = pa.table({"id": ["doc-1"], "name": ["x.pdf"]})
        # op = MyOperator(config=valid_config)
        # tables, metadata = op.transform(table_without_content)
        # assert metadata["skipped_docs_count"] == 1
        pass  # replace with real assertions

    def test_raises_or_records_failure_on_downstream_error(
        self, valid_config: dict, sample_table: pa.Table, mocker
    ) -> None:
        # mocker.patch.object(MyOperator, "_process", side_effect=RuntimeError("boom"))
        # op = MyOperator(config=valid_config)
        # tables, metadata = op.transform(sample_table)
        # assert metadata["failed_docs_count"] == 1
        pass  # replace with real assertions
