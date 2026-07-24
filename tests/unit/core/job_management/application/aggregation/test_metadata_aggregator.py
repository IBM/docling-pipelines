"""
Unit tests for MetadataAggregator - nested metadata handling.

Tests the enterprise-compatible nested node_metadata aggregation.
"""

import pytest

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.application.aggregation.aggregator import MetadataAggregator
from docpipe.core.job_management.application.aggregation.batch_aggregator import (
    BatchProgress,
    ClassificationInfo,
    DocumentStats,
    ExtractionInfo,
    _add_classification_field,
    _add_extraction_stage_fields,
    _add_progress_field,
    _aggregate_document_lists,
    _aggregate_errors,
    _aggregate_extraction_stage_progress,
    _aggregate_time_fields,
    _determine_aggregated_status,
    _extract_classification_from_single_record,
    _extract_from_single_record,
    _get_classification_progress,
    _get_empty_node_stats,
    _get_extraction_progress,
    _get_nested_metadata,
    _inject_metadata_fields,
    _is_classification_operator,
    _is_extraction_operator,
    aggregate_batch_node_stats,
    calculate_finished_batches,
    count_batches_by_status,
)
from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy
from docpipe.core.job_management.domain.models import NodeStats


class TestNestedMetadataAggregation:
    """Test aggregation of structured NodeMetadataItem payloads."""

    def test_structured_metadata_with_nested_node_metadata(self):
        """Test aggregation of structured metadata with nested node_metadata field."""
        aggregator = MetadataAggregator()

        metadata_list = [
            {
                "id": "node-123",
                "operator": "ExtractOperator",
                "node_metadata": {
                    "processed_docs": 10,
                    "total_docs": 20,
                    "node_status": "RUNNING",
                },
            },
            {
                "id": "node-123",
                "operator": "ExtractOperator",
                "node_metadata": {
                    "processed_docs": 15,
                    "total_docs": 20,
                    "node_status": "COMPLETED",
                },
            },
        ]

        result = aggregator.aggregate_metadata(metadata_list=metadata_list)

        # Outer fields preserved from first item
        assert result["id"] == "node-123"
        assert result["operator"] == "ExtractOperator"

        # Inner node_metadata aggregated
        assert "node_metadata" in result
        inner = result["node_metadata"]
        assert inner["processed_docs"] == 25  # SUM strategy
        assert inner["total_docs"] == 40  # SUM strategy
        assert inner["node_status"] == "RUNNING"  # PRIORITY_STATUS strategy

    def test_flat_metadata_backward_compatibility(self):
        """Test that flat metadata (without nested node_metadata) still works."""
        aggregator = MetadataAggregator()

        metadata_list = [
            {"processed_docs": 10, "total_docs": 20, "node_status": "RUNNING"},
            {"processed_docs": 15, "total_docs": 20, "node_status": "COMPLETED"},
        ]

        result = aggregator.aggregate_metadata(metadata_list=metadata_list)

        # Flat aggregation
        assert result["processed_docs"] == 25  # SUM strategy
        assert result["total_docs"] == 40  # SUM strategy
        assert result["node_status"] == "RUNNING"  # PRIORITY_STATUS strategy

    def test_empty_metadata_list(self):
        """Test aggregation with empty metadata list."""
        aggregator = MetadataAggregator()
        result = aggregator.aggregate_metadata(metadata_list=[])
        assert result == {}

    def test_none_metadata_filtered(self):
        """Test that None values are filtered out."""
        aggregator = MetadataAggregator()

        metadata_list = [
            None,
            {
                "id": "node-123",
                "operator": "ExtractOperator",
                "node_metadata": {"processed_docs": 10},
            },
            None,
        ]

        result = aggregator.aggregate_metadata(metadata_list=metadata_list)

        assert result["id"] == "node-123"
        assert result["node_metadata"]["processed_docs"] == 10


class TestDeepMergeEnhanced:
    """Test enhanced _deep_merge with list concatenation and numeric summing."""

    def test_deep_merge_nested_dicts(self):
        """Test deep merge recursively merges nested dictionaries."""
        aggregator = MetadataAggregator()

        dict1 = {"a": {"b": 1, "c": 2}}
        dict2 = {"a": {"b": 3, "d": 4}}

        result = aggregator._deep_merge(dict1=dict1, dict2=dict2)

        assert result["a"]["b"] == 4  # Summed (numeric)
        assert result["a"]["c"] == 2  # From dict1
        assert result["a"]["d"] == 4  # From dict2

    def test_deep_merge_concatenates_lists(self):
        """Test deep merge concatenates lists."""
        aggregator = MetadataAggregator()

        dict1 = {"docs": ["doc1", "doc2"]}
        dict2 = {"docs": ["doc3", "doc4"]}

        result = aggregator._deep_merge(dict1=dict1, dict2=dict2)

        assert result["docs"] == ["doc1", "doc2", "doc3", "doc4"]

    def test_deep_merge_sums_numeric_values(self):
        """Test deep merge sums numeric values (counters)."""
        aggregator = MetadataAggregator()

        dict1 = {"processed_docs": 10, "total_docs": 20}
        dict2 = {"processed_docs": 15, "total_docs": 30}

        result = aggregator._deep_merge(dict1=dict1, dict2=dict2)

        assert result["processed_docs"] == 25
        assert result["total_docs"] == 50

    def test_deep_merge_dict2_wins_for_other_types(self):
        """Test deep merge uses dict2 value for non-dict/list/numeric types."""
        aggregator = MetadataAggregator()

        dict1 = {"status": "RUNNING", "message": "Processing"}
        dict2 = {"status": "COMPLETED", "message": "Done"}

        result = aggregator._deep_merge(dict1=dict1, dict2=dict2)

        assert result["status"] == "COMPLETED"
        assert result["message"] == "Done"


class TestAggregationStrategies:
    """Test various aggregation strategies work correctly."""

    def test_sum_strategy(self):
        """Test SUM strategy aggregates numeric values."""
        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="count", strategy=AggregationStrategy.SUM)

        metadata_list = [{"count": 10}, {"count": 20}, {"count": 30}]
        result = aggregator.aggregate_metadata(metadata_list=metadata_list)

        assert result["count"] == 60

    def test_union_strategy(self):
        """Test UNION strategy deduplicates lists."""
        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="docs", strategy=AggregationStrategy.UNION)

        metadata_list = [
            {"docs": ["doc1", "doc2"]},
            {"docs": ["doc2", "doc3"]},
            {"docs": ["doc3", "doc4"]},
        ]
        result = aggregator.aggregate_metadata(metadata_list=metadata_list)

        assert set(result["docs"]) == {"doc1", "doc2", "doc3", "doc4"}

    def test_last_strategy_default(self):
        """Test LAST strategy is used as default for unknown fields."""
        aggregator = MetadataAggregator()

        metadata_list = [
            {"custom_field": "value1"},
            {"custom_field": "value2"},
            {"custom_field": "value3"},
        ]
        result = aggregator.aggregate_metadata(metadata_list=metadata_list)

        assert result["custom_field"] == "value3"


# ---------------------------------------------------------------------------
# Additional tests to increase coverage for MetadataAggregator / aggregator.py
# ---------------------------------------------------------------------------


class TestRegisterStrategy:
    """Test register_strategy method."""

    def test_register_custom_strategy_requires_function(self):
        """CUSTOM strategy without function raises ValueError."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()

        with pytest.raises(ValueError, match="Custom function required"):
            aggregator.register_strategy(
                field_path="my_field",
                strategy=AggregationStrategy.CUSTOM,
                custom_function=None,
            )

    def test_register_custom_strategy_with_function(self):
        """CUSTOM strategy with function is registered correctly."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(
            field_path="my_field",
            strategy=AggregationStrategy.CUSTOM,
            custom_function=lambda values: sum(values),
        )

        result = aggregator.aggregate_metadata(metadata_list=[{"my_field": 10}, {"my_field": 20}])
        assert result["my_field"] == 30

    def test_register_non_custom_strategy(self):
        """Non-CUSTOM strategy is registered without function."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="counter", strategy=AggregationStrategy.SUM)

        result = aggregator.aggregate_metadata(metadata_list=[{"counter": 5}, {"counter": 7}])
        assert result["counter"] == 12


class TestApplyStrategyBranches:
    """Test all _apply_strategy branches."""

    def test_average_strategy(self):
        """AVERAGE strategy computes mean."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="val", strategy=AggregationStrategy.AVERAGE)

        result = aggregator.aggregate_metadata(metadata_list=[{"val": 10}, {"val": 20}, {"val": 30}])
        assert result["val"] == 20.0

    def test_weighted_average_strategy(self):
        """WEIGHTED_AVERAGE strategy computes mean (same formula as AVERAGE)."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="val", strategy=AggregationStrategy.WEIGHTED_AVERAGE)

        result = aggregator.aggregate_metadata(metadata_list=[{"val": 10}, {"val": 30}])
        assert result["val"] == 20.0

    def test_min_strategy(self):
        """MIN strategy returns minimum value."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="val", strategy=AggregationStrategy.MIN)

        result = aggregator.aggregate_metadata(metadata_list=[{"val": 10}, {"val": 5}, {"val": 20}])
        assert result["val"] == 5

    def test_max_strategy(self):
        """MAX strategy returns maximum value."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="val", strategy=AggregationStrategy.MAX)

        result = aggregator.aggregate_metadata(metadata_list=[{"val": 10}, {"val": 5}, {"val": 20}])
        assert result["val"] == 20

    def test_concat_strategy(self):
        """CONCAT strategy concatenates values including scalars."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="items", strategy=AggregationStrategy.CONCAT)

        result = aggregator.aggregate_metadata(metadata_list=[{"items": ["a", "b"]}, {"items": ["c"]}, {"items": "d"}])
        assert "a" in result["items"]
        assert "d" in result["items"]

    def test_merge_dict_strategy(self):
        """MERGE_DICT strategy shallowly merges dicts (last key wins)."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="cfg", strategy=AggregationStrategy.MERGE_DICT)

        result = aggregator.aggregate_metadata(metadata_list=[{"cfg": {"a": 1}}, {"cfg": {"b": 2, "a": 99}}])
        assert result["cfg"]["a"] == 99
        assert result["cfg"]["b"] == 2

    def test_deep_merge_strategy(self):
        """DEEP_MERGE strategy recursively merges nested dicts."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="nested", strategy=AggregationStrategy.DEEP_MERGE)

        result = aggregator.aggregate_metadata(
            metadata_list=[
                {"nested": {"a": {"x": 1}, "count": 5}},
                {"nested": {"a": {"y": 2}, "count": 3}},
            ]
        )
        assert result["nested"]["a"]["x"] == 1
        assert result["nested"]["a"]["y"] == 2
        assert result["nested"]["count"] == 8  # summed

    def test_first_strategy(self):
        """FIRST strategy returns first value."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="val", strategy=AggregationStrategy.FIRST)

        result = aggregator.aggregate_metadata(metadata_list=[{"val": "first"}, {"val": "second"}, {"val": "third"}])
        assert result["val"] == "first"

    def test_last_completed_strategy(self):
        """LAST_COMPLETED strategy returns last truthy value."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        aggregator.register_strategy(field_path="val", strategy=AggregationStrategy.LAST_COMPLETED)

        result = aggregator.aggregate_metadata(metadata_list=[{"val": "a"}, {"val": "b"}, {"val": "c"}])
        assert result["val"] == "c"

    def test_custom_strategy_without_function_falls_back_to_last(self):
        """CUSTOM strategy with no registered function falls back to LAST."""
        from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy

        aggregator = MetadataAggregator()
        # Register custom without function (bypassing the guard by directly writing)
        aggregator.strategies["val"] = AggregationStrategy.CUSTOM

        result = aggregator.aggregate_metadata(metadata_list=[{"val": "first"}, {"val": "last"}])
        assert result["val"] == "last"

    def test_apply_strategy_all_none_returns_none(self):
        """_apply_strategy returns None when all values are None."""
        aggregator = MetadataAggregator()

        result = aggregator._aggregate_field(metadata_list=[{"val": None}, {"val": None}], field_name="val")
        assert result is None

    def test_union_with_hashable_items(self):
        """UNION strategy deduplicates hashable items preserving order."""

        aggregator = MetadataAggregator()

        result = aggregator._apply_union_strategy(values=[["a", "b", "c"], ["b", "c", "d"]])
        assert result == ["a", "b", "c", "d"]

    def test_union_with_dict_items(self):
        """UNION strategy handles unhashable items (dicts) via str key."""

        aggregator = MetadataAggregator()

        item1 = {"x": 1}
        item2 = {"x": 2}
        result = aggregator._apply_union_strategy(values=[[item1, item2], [item1]])
        # item1 should appear only once
        assert len([r for r in result if r == item1]) == 1


class TestAggregateNestedNodeMetadata:
    """Test _aggregate_nested_node_metadata edge cases."""

    def test_returns_empty_when_no_nested_metadata(self):
        """Returns empty dict when no items have nested node_metadata."""
        aggregator = MetadataAggregator()

        result = aggregator._aggregate_nested_node_metadata(
            metadata_list=[{"id": "x", "operator": "y"}]  # no node_metadata key
        )
        assert result == {}

    def test_skips_non_dict_nested_metadata(self):
        """Items where node_metadata is not a dict are skipped."""
        aggregator = MetadataAggregator()

        result = aggregator._aggregate_nested_node_metadata(
            metadata_list=[
                {"node_metadata": "not_a_dict"},
                {"node_metadata": {"count": 5}},
            ]
        )
        # Only the valid dict entry is aggregated
        assert result.get("count") == 5


# ---------------------------------------------------------------------------
# Tests for batch_aggregator.py functions
# ---------------------------------------------------------------------------


class TestGetEmptyNodeStats:
    """Test _get_empty_node_stats."""

    def test_returns_empty_node_stats(self):
        result = _get_empty_node_stats(node_id="node-1")
        assert result.node_id == "node-1"
        assert result.name == "Unknown"
        assert result.node_status == ExecutionStatus.PENDING.value
        assert result.docs_completed == []


class TestCountBatchesByStatus:
    """Test count_batches_by_status."""

    def test_counts_all_statuses(self):
        records = [
            NodeStats(node_id="n1", name="N", node_status=ExecutionStatus.RUNNING.value),
            NodeStats(node_id="n2", name="N", node_status=ExecutionStatus.COMPLETED.value),
            NodeStats(node_id="n3", name="N", node_status=ExecutionStatus.FAILED.value),
        ]
        counts = count_batches_by_status(batch_records=records)
        assert counts[ExecutionStatus.RUNNING.value] == 1
        assert counts[ExecutionStatus.COMPLETED.value] == 1
        assert counts[ExecutionStatus.FAILED.value] == 1

    def test_unknown_status_not_counted(self):
        records = [NodeStats(node_id="n1", name="N", node_status="CUSTOM_STATUS")]
        counts = count_batches_by_status(batch_records=records)
        # CUSTOM_STATUS is not in the dict so it should remain 0 for known statuses
        assert counts[ExecutionStatus.RUNNING.value] == 0


class TestDetermineAggregatedStatus:
    """Test _determine_aggregated_status."""

    def test_running_when_active_batches(self):
        counts = {
            ExecutionStatus.RUNNING.value: 1,
            ExecutionStatus.COMPLETED.value: 2,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.SKIPPED.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }
        result = _determine_aggregated_status(status_counts=counts, total_batches=3)
        assert result == ExecutionStatus.RUNNING.value

    def test_canceled_when_all_canceled(self):
        counts = {
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.COMPLETED.value: 0,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.CANCELED.value: 3,
            ExecutionStatus.SKIPPED.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }
        result = _determine_aggregated_status(status_counts=counts, total_batches=3)
        assert result == ExecutionStatus.CANCELED.value

    def test_failed_when_all_failed(self):
        counts = {
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.COMPLETED.value: 0,
            ExecutionStatus.FAILED.value: 2,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.SKIPPED.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }
        result = _determine_aggregated_status(status_counts=counts, total_batches=2)
        assert result == ExecutionStatus.FAILED.value

    def test_skipped_when_all_skipped(self):
        counts = {
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.COMPLETED.value: 0,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.SKIPPED.value: 2,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }
        result = _determine_aggregated_status(status_counts=counts, total_batches=2)
        assert result == ExecutionStatus.SKIPPED.value

    def test_completed_with_errors_on_mixed(self):
        counts = {
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.COMPLETED.value: 1,
            ExecutionStatus.FAILED.value: 1,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.SKIPPED.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }
        result = _determine_aggregated_status(status_counts=counts, total_batches=2)
        assert result == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    def test_completed_with_errors_status_present(self):
        counts = {
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.COMPLETED.value: 0,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.SKIPPED.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 1,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }
        result = _determine_aggregated_status(status_counts=counts, total_batches=1)
        assert result == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    def test_completed_with_warnings_status_present(self):
        counts = {
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.COMPLETED.value: 0,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.SKIPPED.value: 0,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 1,
        }
        result = _determine_aggregated_status(status_counts=counts, total_batches=1)
        assert result == ExecutionStatus.COMPLETED_WITH_WARNINGS.value

    def test_completed_when_all_completed_or_skipped(self):
        counts = {
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.COMPLETED.value: 2,
            ExecutionStatus.FAILED.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.SKIPPED.value: 1,
            ExecutionStatus.PENDING.value: 0,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }
        result = _determine_aggregated_status(status_counts=counts, total_batches=3)
        assert result == ExecutionStatus.COMPLETED.value


class TestAggregateTimeFields:
    """Test _aggregate_time_fields."""

    def test_min_start_max_end(self):
        records = [
            NodeStats(node_id="n1", name="N", start_time=100, end_time=200),
            NodeStats(node_id="n2", name="N", start_time=150, end_time=300),
        ]
        start, end, taken = _aggregate_time_fields(batch_records=records)
        assert start == 100
        assert end == 300
        assert taken == 200

    def test_empty_records_returns_zeros(self):
        records = [NodeStats(node_id="n1", name="N", start_time=0, end_time=0)]
        start, end, taken = _aggregate_time_fields(batch_records=records)
        assert start == 0
        assert end == 0
        assert taken == 0


class TestAggregateDocumentLists:
    """Test _aggregate_document_lists."""

    def test_union_deduplicates(self):
        records = [
            NodeStats(
                node_id="n1",
                name="N",
                total_docs=["a", "b"],
                docs_completed=["a"],
                failed_docs=["b"],
                skipped_docs=[],
                col_names=["col1"],
            ),
            NodeStats(
                node_id="n2",
                name="N",
                total_docs=["b", "c"],
                docs_completed=["c"],
                failed_docs=[],
                skipped_docs=["b"],
                col_names=["col1", "col2"],
            ),
        ]
        cols, total, failed, skipped, completed = _aggregate_document_lists(batch_records=records)
        assert total == {"a", "b", "c"}
        assert completed == {"a", "c"}
        assert failed == {"b"}
        assert skipped == {"b"}
        assert cols == {"col1", "col2"}


class TestAggregateErrors:
    """Test _aggregate_errors."""

    def test_joins_errors(self):
        records = [
            NodeStats(node_id="n1", name="N", error="error1"),
            NodeStats(node_id="n2", name="N", error="  "),
            NodeStats(node_id="n3", name="N", error="error2"),
        ]
        result = _aggregate_errors(batch_records=records)
        assert result == "error1 | error2"

    def test_empty_when_no_errors(self):
        records = [NodeStats(node_id="n1", name="N", error="")]
        result = _aggregate_errors(batch_records=records)
        assert result == ""


class TestGetNestedMetadata:
    """Test _get_nested_metadata."""

    def test_returns_inner_node_metadata_when_present(self):
        record = NodeStats(
            node_id="n1",
            name="N",
            node_metadata={"node_metadata": {"count": 5}, "id": "x"},
        )
        result = _get_nested_metadata(record=record)
        assert result == {"count": 5}

    def test_returns_flat_metadata_when_no_nested(self):
        record = NodeStats(
            node_id="n1",
            name="N",
            node_metadata={"count": 5, "status": "RUNNING"},
        )
        result = _get_nested_metadata(record=record)
        assert result == {"count": 5, "status": "RUNNING"}

    def test_returns_none_for_empty_metadata(self):
        record = NodeStats(node_id="n1", name="N", node_metadata={})
        result = _get_nested_metadata(record=record)
        assert result is None

    def test_returns_none_for_non_dict_metadata(self):
        record = NodeStats(node_id="n1", name="N", node_metadata=None)
        result = _get_nested_metadata(record=record)
        assert result is None


class TestIsExtractionAndClassificationOperator:
    """Test _is_extraction_operator and _is_classification_operator."""

    def test_is_extraction_operator_with_legacy_field(self):
        records = [
            NodeStats(
                node_id="n1",
                name="N",
                node_metadata={"extraction_running": 5},
            )
        ]
        assert _is_extraction_operator(batch_records=records) is True

    def test_is_not_extraction_operator(self):
        records = [NodeStats(node_id="n1", name="N", node_metadata={"total_docs": 10})]
        assert _is_extraction_operator(batch_records=records) is False

    def test_is_classification_operator(self):
        records = [
            NodeStats(
                node_id="n1",
                name="N",
                node_metadata={"classification_running": 3},
            )
        ]
        assert _is_classification_operator(batch_records=records) is True

    def test_is_not_classification_operator(self):
        records = [NodeStats(node_id="n1", name="N", node_metadata={"total_docs": 10})]
        assert _is_classification_operator(batch_records=records) is False


class TestExtractFromSingleRecord:
    """Test _extract_from_single_record."""

    def test_legacy_extraction_fields(self):
        metadata = {"extraction_running": 10, "extraction_completed": 7}
        total, completed, weighted = _extract_from_single_record(metadata=metadata)
        assert total == 10
        assert completed == 7
        assert weighted == 7.0
        # Fields removed after reading
        assert "extraction_running" not in metadata

    def test_fallback_to_persistent_fields(self):
        from docpipe.core.constants.constants import Metrics

        metadata = {Metrics.External.TOTAL_DOCS: 5, Metrics.External.PROCESSED_DOCS: 3}
        total, completed, _weighted = _extract_from_single_record(metadata=metadata)
        assert total == 5
        assert completed == 3

    def test_no_fields_returns_zeros(self):
        metadata = {"other_field": "value"}
        total, completed, _weighted = _extract_from_single_record(metadata=metadata)
        assert total == 0
        assert completed == 0
        assert _weighted == 0.0


class TestExtractClassificationFromSingleRecord:
    """Test _extract_classification_from_single_record."""

    def test_extracts_classification_fields(self):
        metadata = {"classification_running": 8, "classification_completed": 5}
        total, completed = _extract_classification_from_single_record(metadata=metadata)
        assert total == 8
        assert completed == 5
        assert "classification_running" not in metadata

    def test_fallback_persistent_fields(self):
        from docpipe.core.constants.constants import Metrics

        metadata = {Metrics.External.TOTAL_DOCS: 4, Metrics.External.PROCESSED_DOCS: 2}
        total, completed = _extract_classification_from_single_record(metadata=metadata)
        assert total == 4
        assert completed == 2


class TestGetExtractionProgress:
    """Test _get_extraction_progress."""

    def test_non_extraction_returns_false(self):
        records = [NodeStats(node_id="n1", name="N", node_metadata={"total_docs": 5})]
        info = _get_extraction_progress(batch_records=records)
        assert info.is_extraction_operator is False
        assert info.total == 0

    def test_extraction_operator_aggregates(self):
        records = [
            NodeStats(
                node_id="n1",
                name="N",
                node_metadata={"extraction_running": 5, "extraction_completed": 3},
            ),
            NodeStats(
                node_id="n2",
                name="N",
                node_metadata={"extraction_running": 4, "extraction_completed": 2},
            ),
        ]
        info = _get_extraction_progress(batch_records=records)
        assert info.is_extraction_operator is True
        assert info.total == 9
        assert info.completed == 5


class TestGetClassificationProgress:
    """Test _get_classification_progress."""

    def test_non_classification_returns_false(self):
        records = [NodeStats(node_id="n1", name="N", node_metadata={"total_docs": 5})]
        info = _get_classification_progress(batch_records=records)
        assert info.is_classification_operator is False

    def test_classification_operator_aggregates(self):
        records = [
            NodeStats(
                node_id="n1",
                name="N",
                node_metadata={"classification_running": 6, "classification_completed": 4},
            )
        ]
        info = _get_classification_progress(batch_records=records)
        assert info.is_classification_operator is True
        assert info.total == 6
        assert info.completed == 4


class TestCalculateFinishedBatches:
    """Test calculate_finished_batches."""

    def test_counts_terminal_statuses(self):
        counts = {
            ExecutionStatus.COMPLETED.value: 3,
            ExecutionStatus.FAILED.value: 1,
            ExecutionStatus.SKIPPED.value: 2,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 1,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.RUNNING.value: 1,
            ExecutionStatus.PENDING.value: 1,
            ExecutionStatus.QUEUED.value: 0,
            ExecutionStatus.CANCELED.value: 0,
            ExecutionStatus.CANCELING.value: 0,
        }
        result = calculate_finished_batches(status_counts=counts)
        assert result == 7  # 3 + 1 + 2 + 1 + 0


class TestAddProgressField:
    """Test _add_progress_field."""

    def test_adds_progress_string(self):
        metadata = {}
        from docpipe.core.constants.constants import ExecutionStatus

        counts = {
            ExecutionStatus.COMPLETED.value: 2,
            ExecutionStatus.FAILED.value: 1,
            ExecutionStatus.RUNNING.value: 0,
            ExecutionStatus.SKIPPED.value: 1,
            ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
            ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
        }
        _add_progress_field(metadata=metadata, finished_batches=3, total_batches=5, status_counts=counts)

        from docpipe.core.constants.operator_constants import OperatorConstants

        assert OperatorConstants.Metadata.FIELD_PROGRESS in metadata
        assert "3 of 5" in metadata[OperatorConstants.Metadata.FIELD_PROGRESS]

    def test_no_progress_when_zero_total(self):
        metadata = {}
        counts = {ExecutionStatus.COMPLETED.value: 0}
        _add_progress_field(metadata=metadata, finished_batches=0, total_batches=0, status_counts=counts)

        from docpipe.core.constants.operator_constants import OperatorConstants

        assert OperatorConstants.Metadata.FIELD_PROGRESS not in metadata


class TestAddExtractionStageFields:
    """Test _add_extraction_stage_fields."""

    def test_skips_when_no_stage_progress(self):
        metadata = {}
        info = ExtractionInfo(total=10, completed=5, is_extraction_operator=True, stage_progress=None)
        _add_extraction_stage_fields(metadata=metadata, extraction_info=info, has_pending_batches=False)
        assert metadata == {}

    def test_adds_text_extraction_field(self):
        metadata = {}
        info = ExtractionInfo(
            total=10,
            completed=5,
            is_extraction_operator=True,
            stage_progress={"text_extraction": {"documents_total": 10, "documents_completed": 5}},
        )
        _add_extraction_stage_fields(metadata=metadata, extraction_info=info, has_pending_batches=False)

        from docpipe.core.constants.operator_constants import OperatorConstants

        assert OperatorConstants.Metadata.FIELD_TEXT_EXTRACTED in metadata

    def test_adds_entity_extraction_field(self):
        metadata = {}
        info = ExtractionInfo(
            total=10,
            completed=5,
            is_extraction_operator=True,
            stage_progress={"entity_extraction": {"documents_total": 10, "documents_completed": 5}},
        )
        _add_extraction_stage_fields(metadata=metadata, extraction_info=info, has_pending_batches=False)

        from docpipe.core.constants.operator_constants import OperatorConstants

        assert OperatorConstants.Metadata.FIELD_ENTITIES_EXTRACTED in metadata

    def test_pending_adds_more_in_queue(self):
        metadata = {}
        info = ExtractionInfo(
            total=10,
            completed=3,
            is_extraction_operator=True,
            stage_progress={"text_extraction": {"documents_total": 10, "documents_completed": 3}},
        )
        _add_extraction_stage_fields(metadata=metadata, extraction_info=info, has_pending_batches=True)

        from docpipe.core.constants.operator_constants import OperatorConstants

        assert "more in queue" in metadata.get(OperatorConstants.Metadata.FIELD_TEXT_EXTRACTED, "")

    def test_generic_stage_name_used_as_field(self):
        metadata = {}
        info = ExtractionInfo(
            total=10,
            completed=5,
            is_extraction_operator=True,
            stage_progress={"custom_stage": {"documents_total": 10, "documents_completed": 5}},
        )
        _add_extraction_stage_fields(metadata=metadata, extraction_info=info, has_pending_batches=False)
        # custom_stage becomes "Custom Stage" as a field name
        assert "Custom Stage" in metadata


class TestAddClassificationField:
    """Test _add_classification_field."""

    def test_skips_when_zero_total(self):
        metadata = {}
        info = ClassificationInfo(total=0, completed=0, is_classification_operator=True)
        _add_classification_field(metadata=metadata, classification_info=info, has_pending_batches=False)
        assert metadata == {}

    def test_adds_classification_percentage(self):
        metadata = {}
        info = ClassificationInfo(total=10, completed=8, is_classification_operator=True)
        _add_classification_field(metadata=metadata, classification_info=info, has_pending_batches=False)

        from docpipe.core.constants.operator_constants import OperatorConstants

        assert OperatorConstants.Metadata.FIELD_DOCS_CLASSIFIED in metadata
        assert "80.0%" in metadata[OperatorConstants.Metadata.FIELD_DOCS_CLASSIFIED]

    def test_pending_adds_more_in_queue(self):
        metadata = {}
        info = ClassificationInfo(total=10, completed=3, is_classification_operator=True)
        _add_classification_field(metadata=metadata, classification_info=info, has_pending_batches=True)

        from docpipe.core.constants.operator_constants import OperatorConstants

        assert "more in queue" in metadata[OperatorConstants.Metadata.FIELD_DOCS_CLASSIFIED]


class TestInjectMetadataFields:
    """Test _inject_metadata_fields."""

    def test_injects_core_fields(self):
        aggregated_metadata = {}
        from docpipe.core.constants.constants import ExecutionStatus, Metrics

        doc_stats = DocumentStats(total_expected=10, completed=8, processed=9)
        batch_progress = BatchProgress(
            finished=2,
            total=3,
            has_pending=True,
            status_counts={
                ExecutionStatus.COMPLETED.value: 2,
                ExecutionStatus.RUNNING.value: 1,
                ExecutionStatus.FAILED.value: 0,
                ExecutionStatus.SKIPPED.value: 0,
                ExecutionStatus.COMPLETED_WITH_ERRORS.value: 0,
                ExecutionStatus.COMPLETED_WITH_WARNINGS.value: 0,
                ExecutionStatus.PENDING.value: 0,
                ExecutionStatus.QUEUED.value: 0,
                ExecutionStatus.CANCELED.value: 0,
                ExecutionStatus.CANCELING.value: 0,
            },
        )
        extraction_info = ExtractionInfo(total=0, completed=0, is_extraction_operator=False)
        classification_info = ClassificationInfo(total=0, completed=0, is_classification_operator=False)

        _inject_metadata_fields(
            aggregated_metadata=aggregated_metadata,
            aggregated_status=ExecutionStatus.RUNNING.value,
            doc_stats=doc_stats,
            batch_progress=batch_progress,
            extraction_info=extraction_info,
            classification_info=classification_info,
        )

        inner = aggregated_metadata["node_metadata"]
        assert inner[Metrics.External.TOTAL_DOCS] == 10
        assert inner[Metrics.External.COMPLETED_DOCS_COUNT] == 8
        assert inner[Metrics.External.PROCESSED_DOCS] == 9
        assert inner[Metrics.External.NODE_STATUS] == ExecutionStatus.RUNNING.value


class TestAggregateBatchNodeStats:
    """Test aggregate_batch_node_stats end-to-end."""

    def test_empty_batch_returns_empty_node(self):
        aggregator = MetadataAggregator()
        result = aggregate_batch_node_stats(node_id="n1", batch_records=[], aggregator=aggregator)
        assert result.node_id == "n1"
        assert result.node_status == ExecutionStatus.PENDING.value

    def test_single_completed_batch(self):
        aggregator = MetadataAggregator()
        records = [
            NodeStats(
                node_id="n1",
                name="MyNode",
                start_time=1000,
                end_time=2000,
                node_status=ExecutionStatus.COMPLETED.value,
                total_docs=["doc1", "doc2"],
                docs_completed=["doc1", "doc2"],
                failed_docs=[],
                skipped_docs=[],
                col_names=["col1"],
                node_metadata={"node_metadata": {"total_docs_count": 2}},
            )
        ]
        result = aggregate_batch_node_stats(node_id="n1", batch_records=records, aggregator=aggregator)
        assert result.node_id == "n1"
        assert result.node_status == ExecutionStatus.COMPLETED.value
        assert result.docs_completed_count == 2

    def test_mixed_statuses_aggregated(self):
        aggregator = MetadataAggregator()
        records = [
            NodeStats(
                node_id="n1",
                name="MyNode",
                node_status=ExecutionStatus.COMPLETED.value,
                total_docs=["doc1"],
                docs_completed=["doc1"],
                failed_docs=[],
                skipped_docs=[],
            ),
            NodeStats(
                node_id="n1",
                name="MyNode",
                node_status=ExecutionStatus.FAILED.value,
                total_docs=["doc2"],
                docs_completed=[],
                failed_docs=["doc2"],
                skipped_docs=[],
                error="fail",
            ),
        ]
        result = aggregate_batch_node_stats(node_id="n1", batch_records=records, aggregator=aggregator)
        assert result.node_status == ExecutionStatus.COMPLETED_WITH_ERRORS.value
        assert "fail" in result.error


class TestAggregateExtractionStageProgress:
    """Test _aggregate_extraction_stage_progress."""

    def test_running_batch_with_stage_progress(self):
        from docpipe.core.constants.operator_constants import OperatorConstants

        records = [
            NodeStats(
                node_id="n1",
                name="N",
                node_status=ExecutionStatus.RUNNING.value,
                node_metadata={
                    "node_metadata": {
                        OperatorConstants.Metadata.EXTRACTION_STAGE_PROGRESS: {
                            "text_extraction": {
                                OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL: 10,
                                OperatorConstants.Extraction.STAGE_DOCUMENTS_COMPLETED: 5,
                                OperatorConstants.Extraction.STAGE_DOCUMENTS_FAILED: 0,
                                OperatorConstants.Extraction.STAGE_STATUS: "running",
                            }
                        }
                    }
                },
            )
        ]
        result = _aggregate_extraction_stage_progress(batch_records=records)
        assert "text_extraction" in result
        assert result["text_extraction"][OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL] == 10

    def test_completed_batch_updates_stages(self):
        from docpipe.core.constants.constants import Metrics
        from docpipe.core.constants.operator_constants import OperatorConstants

        records = [
            NodeStats(
                node_id="n1",
                name="N",
                node_status=ExecutionStatus.COMPLETED.value,
                node_metadata={
                    "node_metadata": {
                        Metrics.External.TOTAL_DOCS: 5,
                        Metrics.External.PROCESSED_DOCS: 5,
                    }
                },
            )
        ]
        result = _aggregate_extraction_stage_progress(batch_records=records)
        assert "text_extraction" in result
        assert result["text_extraction"][OperatorConstants.Extraction.STAGE_DOCUMENTS_TOTAL] == 5
