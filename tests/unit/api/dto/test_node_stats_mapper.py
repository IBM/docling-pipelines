"""
Unit tests for NodeStatsMapper.to_log_string() — all permutations.

Scenarios covered:

  SKIPPED
    1.  Skipped with reason
    2.  Skipped without reason (fallback default text)

  COMPLETED (non-batched)
    3.  Completed — no schema, no metadata
    4.  Completed — with schema, no metadata
    5.  Completed — no schema, with metadata (scalars only)
    6.  Completed — with schema + metadata containing list fields (failed_docs / skipped_docs)
    7.  Completed — metadata uses raw dict (no inner node_metadata wrapper)

  FAILED (non-batched)
    8.  Failed — with error message
    9.  Failed — multiline error (newlines collapsed)
    10. Failed — no error message

  OTHER TERMINAL STATES (non-batched)
    11. CompletedWithErrors — shows "Completed execution" footer
    12. CompletedWithWarnings — shows "Completed execution" footer
    13. Canceled
    14. Aborted

  NON-TERMINAL / IN-PROGRESS (non-batched)
    15. Pending — renders block, 0 docs, 0.00 s

  BATCHED — all batches pass
    16. All batches Completed — no Error Details section
    17. Single batch

  BATCHED — failures
    18. One batch failed — Error Details section present, only that batch listed
    19. Two batches failed — both listed in Error Details
    20. All batches failed

  BATCHED — mixed with skipped batches
    21. Some batches Skipped (fail-fast) — Skipped batches NOT in Error Details
    22. CompletedWithErrors + skipped batches — only failed in Error Details

  BATCHED — batch_num is None
    23. batch_num=None sorts as 0, renders "Batch None"

  STRUCTURAL / EDGE CASES
    24. Empty batch_stats dict {} — treated same as None (no batch section)
    25. Empty col_names — no Schema section
    26. node_metadata is None — no Operator Metadata section
    27. node_metadata inner value is a list — still rendered in JSON dump
    28. All sections present together (completed, schema, batches, metadata)
"""

import pytest

from docpipe.api.dto.mappers.node_stats_mapper import _BORDER, _END, _THIN, NodeStatsMapper
from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.domain.models.node_stats import NodeStats

NODE_ID = "4a6143a8-8bac-4d46-8aea-a08ec065d752"
NODE_NAME = "Chunking"


def _node(
    *,
    status: str = ExecutionStatus.COMPLETED.value,
    error: str = "",
    col_names: list[str] | None = None,
    node_metadata: dict | None = None,
    time_taken: int = 10,
    total_docs: list[str] | None = None,
) -> NodeStats:
    return NodeStats(
        id=NODE_ID,
        name=NODE_NAME,
        node_status=status,
        error=error,
        col_names=col_names or [],
        node_metadata=node_metadata,
        time_taken=time_taken,
        total_docs=total_docs or ["doc-1", "doc-2"],
    )


def _batch(
    *,
    batch_num: int | None,
    status: str = ExecutionStatus.COMPLETED.value,
    error: str = "",
    docs: list[str] | None = None,
    time_taken: int = 4,
) -> NodeStats:
    return NodeStats(
        id=NODE_ID,
        name=NODE_NAME,
        node_status=status,
        error=error,
        batch_num=batch_num,
        total_docs=docs or ["doc-1"],
        time_taken=time_taken,
    )


def _log(node_stat: NodeStats, batch_stats: dict | None = None) -> str:
    return NodeStatsMapper.to_log_string(node_id=NODE_ID, node_stat=node_stat, batch_stats=batch_stats)


# ── helpers ────────────────────────────────────────────────────────────────────


def _lines(output: str) -> list[str]:
    return output.split("\n")


def _has_section(output: str, label: str) -> bool:
    return any(line.strip() == label or line.startswith(label) for line in _lines(output))


# ══════════════════════════════════════════════════════════════════════════════
# SKIPPED
# ══════════════════════════════════════════════════════════════════════════════


class TestSkipped:
    def test_skipped_with_reason(self):
        out = _log(_node(status=ExecutionStatus.SKIPPED.value, error="no docs ingested"))
        lines = _lines(out)
        assert lines[0] == _BORDER
        assert lines[1] == f"  Step: {NODE_NAME}"
        assert lines[2] == f"  ID:   {NODE_ID}"
        assert lines[3] == _THIN
        assert lines[4] == f"Step ID: {NODE_ID}"
        assert "no docs ingested" in lines[5]
        assert len(lines) == 6  # no footer

    def test_skipped_without_reason_uses_default(self):
        out = _log(_node(status=ExecutionStatus.SKIPPED.value, error=""))
        assert "no input data available for processing" in out

    def test_skipped_no_footer_separator(self):
        out = _log(_node(status=ExecutionStatus.SKIPPED.value, error="reason"))
        assert _END not in out

    def test_skipped_no_batch_section(self):
        out = _log(_node(status=ExecutionStatus.SKIPPED.value), batch_stats={"b1": _batch(batch_num=1)})
        assert "Batch Execution Summary" not in out

    def test_skipped_multiline_error_collapsed(self):
        out = _log(_node(status=ExecutionStatus.SKIPPED.value, error="line1\nline2"))
        assert "\n\n" not in out
        assert "line1 line2" in out


# ══════════════════════════════════════════════════════════════════════════════
# COMPLETED — non-batched
# ══════════════════════════════════════════════════════════════════════════════


class TestCompleted:
    def test_block_structure_present(self):
        out = _log(_node())
        lines = _lines(out)
        assert lines[0] == _BORDER
        assert lines[1] == f"  Step: {NODE_NAME}"
        assert lines[2] == f"  ID:   {NODE_ID}"
        assert lines[3] == _THIN
        assert lines[4] == f"Starting execution: Step Name: {NODE_NAME}"
        assert lines[-1] == _END
        assert _THIN in lines[-3]

    def test_no_schema_when_col_names_empty(self):
        out = _log(_node(col_names=[]))
        assert "Schema:" not in out

    def test_schema_present_when_col_names_given(self):
        out = _log(_node(col_names=["id", "content", "path"]))
        assert "Schema:" in out
        assert "id: string" in out
        assert "content: string" in out
        assert "path: string" in out

    def test_no_metadata_section_when_none(self):
        out = _log(_node(node_metadata=None))
        assert "Operator Metadata" not in out

    def test_metadata_inner_dict_shown_as_json(self):
        meta = {"node_metadata": {"node_status": "Completed", "processed_docs": 42}}
        out = _log(_node(node_metadata=meta))
        assert "Operator Metadata" in out
        assert '"node_status": "Completed"' in out
        assert '"processed_docs": 42' in out

    def test_metadata_list_fields_shown_in_json(self):
        """failed_docs / skipped_docs lists must appear in the JSON dump."""
        meta = {
            "node_metadata": {
                "node_status": "Completed",
                "failed_docs": [{"id": "d1", "name": "file.pdf", "reason": "empty"}],
            }
        }
        out = _log(_node(node_metadata=meta))
        assert '"failed_docs"' in out
        assert "file.pdf" in out

    def test_metadata_raw_dict_no_wrapper(self):
        """If node_metadata has no inner 'node_metadata' key, use it directly."""
        meta = {"node_status": "Completed", "processed_docs": 5}
        out = _log(_node(node_metadata=meta))
        assert "Operator Metadata" in out
        assert '"processed_docs": 5' in out

    def test_no_error_section_when_no_error(self):
        out = _log(_node(error=""))
        assert "Error Details" not in out

    def test_footer_shows_completed(self):
        out = _log(_node(time_taken=12))
        assert "Completed execution: Chunking,  time= 12.00 seconds" in out

    def test_footer_shows_time(self):
        out = _log(_node(time_taken=7))
        assert "7.00 seconds" in out


# ══════════════════════════════════════════════════════════════════════════════
# FAILED — non-batched
# ══════════════════════════════════════════════════════════════════════════════


class TestFailed:
    def test_footer_shows_failed(self):
        out = _log(_node(status=ExecutionStatus.FAILED.value, error="Ollama unreachable"))
        assert "Failed execution: Chunking" in out

    def test_error_section_present(self):
        out = _log(_node(status=ExecutionStatus.FAILED.value, error="Ollama unreachable"))
        assert "Error Details" in out
        assert "Ollama unreachable" in out

    def test_multiline_error_collapsed(self):
        out = _log(_node(status=ExecutionStatus.FAILED.value, error="line1\nline2\nline3"))
        assert "line1 line2 line3" in out
        # no raw newlines within the error value itself
        assert "line1\n" not in out

    def test_no_error_section_when_error_empty(self):
        out = _log(_node(status=ExecutionStatus.FAILED.value, error=""))
        assert "Error Details" not in out

    def test_end_separator_present(self):
        out = _log(_node(status=ExecutionStatus.FAILED.value, error="oops"))
        assert _END in out


# ══════════════════════════════════════════════════════════════════════════════
# OTHER TERMINAL / NON-TERMINAL STATES
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "status",
    [
        ExecutionStatus.COMPLETED_WITH_ERRORS.value,
        ExecutionStatus.COMPLETED_WITH_WARNINGS.value,
        ExecutionStatus.CANCELED.value,
        ExecutionStatus.ABORTED.value,
    ],
)
def test_non_failed_terminal_states_show_completed_footer(status):
    out = _log(_node(status=status))
    assert "Completed execution:" in out
    assert _END in out


def test_pending_renders_block():
    """Non-terminal Pending state still produces a valid block."""
    out = _log(_node(status=ExecutionStatus.PENDING.value, time_taken=0))
    assert _BORDER in out
    assert "Starting execution:" in out
    assert "0.00 seconds" in out
    assert _END in out


# ══════════════════════════════════════════════════════════════════════════════
# BATCHED — all pass
# ══════════════════════════════════════════════════════════════════════════════


class TestBatchedAllPass:
    def _batches(self) -> dict[str, NodeStats]:
        return {
            "b1": _batch(batch_num=1),
            "b2": _batch(batch_num=2),
            "b3": _batch(batch_num=3),
        }

    def test_batch_section_present(self):
        out = _log(_node(), self._batches())
        assert "Batch Execution Summary (3 batches):" in out

    def test_all_batches_listed_in_order(self):
        out = _log(_node(), self._batches())
        lines = _lines(out)
        batch_lines = [ln for ln in lines if "Batch" in ln and "Summary" not in ln and "Error" not in ln]
        assert "Batch 1" in batch_lines[0]
        assert "Batch 2" in batch_lines[1]
        assert "Batch 3" in batch_lines[2]

    def test_no_error_details_section(self):
        out = _log(_node(), self._batches())
        assert "Error Details" not in out

    def test_single_batch(self):
        out = _log(_node(), {"b1": _batch(batch_num=1)})
        assert "Batch Execution Summary (1 batches):" in out
        assert "1 doc)" in out  # singular

    def test_doc_plural(self):
        out = _log(_node(), {"b1": _batch(batch_num=1, docs=["d1", "d2"])})
        assert "2 docs)" in out


# ══════════════════════════════════════════════════════════════════════════════
# BATCHED — failures
# ══════════════════════════════════════════════════════════════════════════════


class TestBatchedFailures:
    def test_one_failed_batch_in_error_details(self):
        batches = {
            "b1": _batch(batch_num=1),
            "b2": _batch(batch_num=2, status=ExecutionStatus.FAILED.value, error="Timeout"),
            "b3": _batch(batch_num=3),
        }
        out = _log(_node(status=ExecutionStatus.COMPLETED_WITH_ERRORS.value), batches)
        assert "Error Details:" in out
        assert "Batch 2: Timeout" in out
        assert "Batch 1" not in out.split("Error Details:")[1]
        assert "Batch 3" not in out.split("Error Details:")[1]

    def test_two_failed_batches_both_in_error_details(self):
        batches = {
            "b1": _batch(batch_num=1),
            "b2": _batch(batch_num=2, status=ExecutionStatus.FAILED.value, error="Timeout"),
            "b3": _batch(batch_num=3, status=ExecutionStatus.FAILED.value, error="OOM"),
            "b4": _batch(batch_num=4),
        }
        out = _log(_node(status=ExecutionStatus.COMPLETED_WITH_ERRORS.value), batches)
        error_section = out.split("Error Details:")[1]
        assert "Batch 2: Timeout" in error_section
        assert "Batch 3: OOM" in error_section

    def test_all_batches_failed(self):
        batches = {
            "b1": _batch(batch_num=1, status=ExecutionStatus.FAILED.value, error="err1"),
            "b2": _batch(batch_num=2, status=ExecutionStatus.FAILED.value, error="err2"),
        }
        out = _log(_node(status=ExecutionStatus.FAILED.value), batches)
        assert "Batch 1: err1" in out
        assert "Batch 2: err2" in out

    def test_no_node_level_error_section_for_batched_nodes(self):
        """Aggregated node error must NOT appear as a top-level Error Details block."""
        batches = {"b1": _batch(batch_num=1, status=ExecutionStatus.FAILED.value, error="err")}
        # Aggregated node error is pipe-joined from batch errors
        node = _node(status=ExecutionStatus.FAILED.value, error="err")
        out = _log(node, batches)
        # Error Details appears once (from batch section), not twice
        assert out.count("Error Details") == 1

    def test_completed_with_errors_batch_in_error_details(self):
        batches = {
            "b1": _batch(batch_num=1, status=ExecutionStatus.COMPLETED_WITH_ERRORS.value, error="partial"),
        }
        out = _log(_node(status=ExecutionStatus.COMPLETED_WITH_ERRORS.value), batches)
        assert "Batch 1: partial" in out


# ══════════════════════════════════════════════════════════════════════════════
# BATCHED — skipped batches (fail-fast)
# ══════════════════════════════════════════════════════════════════════════════


class TestBatchedSkipped:
    def test_skipped_batch_not_in_error_details(self):
        batches = {
            "b1": _batch(batch_num=1),
            "b2": _batch(batch_num=2, status=ExecutionStatus.FAILED.value, error="Crash"),
            "b3": _batch(batch_num=3, status=ExecutionStatus.SKIPPED.value, error="pipeline failed"),
        }
        out = _log(_node(status=ExecutionStatus.COMPLETED_WITH_ERRORS.value), batches)
        error_section = out.split("Error Details:")[1]
        assert "Batch 2: Crash" in error_section
        assert "Batch 3" not in error_section

    def test_skipped_batch_row_shown_in_summary(self):
        batches = {"b1": _batch(batch_num=1, status=ExecutionStatus.SKIPPED.value)}
        out = _log(_node(), batches)
        assert "Batch 1" in out
        assert "Skipped" in out


# ══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_batch_stats_dict_no_batch_section(self):
        out = _log(_node(), batch_stats={})
        assert "Batch Execution Summary" not in out

    def test_batch_num_none_renders_safely(self):
        batches = {"b1": _batch(batch_num=None)}
        out = _log(_node(), batches)
        assert "Batch None" in out

    def test_batches_sorted_by_batch_num(self):
        batches = {
            "b3": _batch(batch_num=3),
            "b1": _batch(batch_num=1),
            "b2": _batch(batch_num=2),
        }
        out = _log(_node(), batches)
        idx1 = out.index("Batch 1")
        idx2 = out.index("Batch 2")
        idx3 = out.index("Batch 3")
        assert idx1 < idx2 < idx3

    def test_batch_error_multiline_collapsed(self):
        batches = {"b1": _batch(batch_num=1, status=ExecutionStatus.FAILED.value, error="line1\nline2")}
        out = _log(_node(status=ExecutionStatus.FAILED.value), batches)
        assert "line1 line2" in out

    def test_metadata_none_no_section(self):
        out = _log(_node(node_metadata=None))
        assert "Operator Metadata" not in out

    def test_metadata_empty_dict_no_section(self):
        out = _log(_node(node_metadata={}))
        assert "Operator Metadata" not in out

    def test_all_sections_together(self):
        """Completed node with schema + batches + metadata — all sections present."""
        meta = {"node_metadata": {"node_status": "Completed", "processed_docs": 300}}
        batches = {
            "b1": _batch(batch_num=1),
            "b2": _batch(batch_num=2),
        }
        out = _log(_node(col_names=["id", "content"], node_metadata=meta), batches)
        assert _BORDER in out
        assert "Starting execution:" in out
        assert "Schema:" in out
        assert "id: string" in out
        assert "Batch Execution Summary (2 batches):" in out
        assert "Operator Metadata" in out
        assert '"processed_docs": 300' in out
        assert "Completed execution:" in out
        assert _END in out

    def test_output_is_valid_string_no_exceptions(self):
        """Smoke test — every combination must not raise."""
        statuses = [
            ExecutionStatus.COMPLETED.value,
            ExecutionStatus.FAILED.value,
            ExecutionStatus.SKIPPED.value,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value,
            ExecutionStatus.CANCELED.value,
            ExecutionStatus.PENDING.value,
        ]
        batches_options = [
            None,
            {},
            {"b1": _batch(batch_num=1)},
            {"b1": _batch(batch_num=1, status=ExecutionStatus.FAILED.value, error="err")},
        ]
        meta_options = [
            None,
            {"node_metadata": {"node_status": "Completed"}},
            {"node_status": "Completed"},
        ]
        for status in statuses:
            for batches in batches_options:
                for meta in meta_options:
                    node = _node(status=status, node_metadata=meta)
                    result = _log(node, batches)
                    assert isinstance(result, str)
                    assert len(result) > 0
