"""Unit tests for LanguageDetect._handle_detection_error."""

from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.language_detection.lang_id import LanguageDetect


def _make_operator(*, filter_value: bool) -> LanguageDetect:
    """Build a LanguageDetect instance with a mocked adapter."""
    with patch(
        "docpipe.core.operators.quality.language_detection.lang_id.LanguageAdapterFactory.create"
    ) as mock_create:
        mock_create.return_value = MagicMock()
        return LanguageDetect(
            {
                "doc_column": "content",
                OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: filter_value,
            }
        )


def _make_table(docs: list[str]) -> pa.Table:
    """Build a minimal table with id, content, and name columns."""
    n = len(docs)
    return pa.Table.from_arrays(
        [
            pa.array([str(i) for i in range(n)]),
            pa.array(docs),
            pa.array([f"doc_{i}.txt" for i in range(n)]),
        ],
        names=[OperatorConstants.Columns.ID, "content", OperatorConstants.Columns.NAME],
    )


class TestHandleDetectionErrorFilterTrue:
    """filter_value=True: failed docs are removed and recorded."""

    @pytest.fixture
    def op(self):
        return _make_operator(filter_value=True)

    def test_appends_row_index_to_remove_list(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)
        remove_row_idx: list[int] = []

        op._handle_detection_error(
            e=ValueError("lang error"),
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=remove_row_idx,
            message="",
        )

        assert 0 in remove_row_idx

    def test_records_failed_document_in_metadata(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)

        op._handle_detection_error(
            e=ValueError("lang error"),
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=[],
            message="",
        )

        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1

    def test_sets_node_status_to_completed_with_errors(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)

        op._handle_detection_error(
            e=ValueError("lang error"),
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=[],
            message="",
        )

        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    def test_sets_message_on_first_failure(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)

        msg = op._handle_detection_error(
            e=ValueError("lang error"),
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=[],
            message="",
        )

        assert msg == "Documents with no language detected are removed from the flow"

    def test_does_not_overwrite_message_on_subsequent_failures(self, op):
        table = _make_table(["a", "b"])
        metadata = op.create_base_metadata(total_docs_count=2)
        existing_message = "Documents with no language detected are removed from the flow"

        msg = op._handle_detection_error(
            e=ValueError("second error"),
            idx=1,
            file_name="doc_1.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=[],
            message=existing_message,
        )

        assert msg == existing_message

    def test_uses_exception_str_when_no_message_attr(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)

        e = RuntimeError("plain string error")
        msg = op._handle_detection_error(
            e=e,
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=[],
            message="",
        )

        # The reason stored in failed_docs should contain the exception text
        assert "plain string error" in metadata[Metrics.External.FAILED_DOCS][0]["reason"]
        assert msg  # message is set


class TestHandleDetectionErrorFilterFalse:
    """filter_value=False: row kept, language set to UNKNOWN."""

    @pytest.fixture
    def op(self):
        return _make_operator(filter_value=False)

    def test_appends_unknown_language(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)
        language_name_column: list[str] = []

        op._handle_detection_error(
            e=ValueError("lang error"),
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=language_name_column,
            language_score_column=[],
            remove_row_idx=[],
            message="",
        )

        assert language_name_column == ["UNKNOWN"]

    def test_appends_zero_score(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)
        language_score_column: list[float] = []

        op._handle_detection_error(
            e=ValueError("lang error"),
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=language_score_column,
            remove_row_idx=[],
            message="",
        )

        assert language_score_column == [0.0]

    def test_sets_node_status_to_completed_with_warnings(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)

        op._handle_detection_error(
            e=ValueError("lang error"),
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=[],
            message="",
        )

        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_WARNINGS.value

    def test_does_not_append_to_remove_row_idx(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)
        remove_row_idx: list[int] = []

        op._handle_detection_error(
            e=ValueError("lang error"),
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=remove_row_idx,
            message="",
        )

        assert remove_row_idx == []

    def test_sets_message_on_first_failure(self, op):
        table = _make_table(["some text"])
        metadata = op.create_base_metadata(total_docs_count=1)

        msg = op._handle_detection_error(
            e=ValueError("lang error"),
            idx=0,
            file_name="doc_0.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=[],
            message="",
        )

        assert msg == "Documents with no language detected are marked as UNKNOWN"

    def test_does_not_overwrite_message_on_subsequent_failures(self, op):
        table = _make_table(["a", "b"])
        metadata = op.create_base_metadata(total_docs_count=2)
        existing_message = "Documents with no language detected are marked as UNKNOWN"

        msg = op._handle_detection_error(
            e=ValueError("second error"),
            idx=1,
            file_name="doc_1.txt",
            table=table,
            metadata=metadata,
            language_name_column=[],
            language_score_column=[],
            remove_row_idx=[],
            message=existing_message,
        )

        assert msg == existing_message
