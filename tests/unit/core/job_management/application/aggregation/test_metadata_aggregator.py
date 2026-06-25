"""
Unit tests for MetadataAggregator - nested metadata handling.

Tests the enterprise-compatible nested node_metadata aggregation.
"""

from docpipe.core.job_management.application.aggregation.aggregator import MetadataAggregator
from docpipe.core.job_management.application.aggregation.strategies import AggregationStrategy


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
