"""
Unit tests for normalization utilities.

Tests cover:
- Normalization of node_stats data for backward compatibility
- Handling of old format with 'id' field
- Handling of new format with 'node_id' field
- Edge cases and empty data
"""

from docpipe.core.constants import DocpipeConstants, OperatorConstants
from docpipe.core.job_management.domain.utils.normalization import normalize_node_stats_for_dto


class TestNormalizeNodeStatsForDto:
    """Test normalize_node_stats_for_dto function."""

    def test_normalize_old_format_with_id(self):
        """Should add node_id field when only id exists (old format)."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            DocpipeConstants.NODE_STATS: {
                "node-1": {
                    OperatorConstants.Misc.ID: "node-1",
                    "name": "TestNode",
                    "status": "COMPLETED",
                }
            },
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # Should add node_id field
        node_data = result[DocpipeConstants.NODE_STATS]["node-1"]
        assert DocpipeConstants.NODE_ID in node_data
        assert node_data[DocpipeConstants.NODE_ID] == "node-1"
        # Original id field should still exist
        assert OperatorConstants.Misc.ID in node_data

    def test_normalize_new_format_with_node_id(self):
        """Should not modify data that already has node_id (new format)."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            DocpipeConstants.NODE_STATS: {
                "node-1": {
                    DocpipeConstants.NODE_ID: "node-1",
                    "name": "TestNode",
                    "status": "COMPLETED",
                }
            },
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # Should return unchanged
        node_data = result[DocpipeConstants.NODE_STATS]["node-1"]
        assert DocpipeConstants.NODE_ID in node_data
        assert node_data[DocpipeConstants.NODE_ID] == "node-1"
        # Should not have added anything
        assert len(node_data) == 3

    def test_normalize_multiple_nodes_old_format(self):
        """Should normalize all nodes in old format."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            DocpipeConstants.NODE_STATS: {
                "node-1": {
                    OperatorConstants.Misc.ID: "node-1",
                    "name": "Node1",
                },
                "node-2": {
                    OperatorConstants.Misc.ID: "node-2",
                    "name": "Node2",
                },
                "node-3": {
                    OperatorConstants.Misc.ID: "node-3",
                    "name": "Node3",
                },
            },
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # All nodes should have node_id
        for node_key in ["node-1", "node-2", "node-3"]:
            node_data = result[DocpipeConstants.NODE_STATS][node_key]
            assert DocpipeConstants.NODE_ID in node_data
            assert node_data[DocpipeConstants.NODE_ID] == node_key

    def test_normalize_empty_node_stats(self):
        """Should handle empty node_stats dict."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            DocpipeConstants.NODE_STATS: {},
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # Should return unchanged
        assert result[DocpipeConstants.NODE_STATS] == {}

    def test_normalize_missing_node_stats(self):
        """Should handle missing node_stats field."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # Should return unchanged
        assert DocpipeConstants.NODE_STATS not in result

    def test_normalize_node_stats_not_dict(self):
        """Should handle node_stats that is not a dict."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            DocpipeConstants.NODE_STATS: "not a dict",
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # Should return unchanged
        assert result[DocpipeConstants.NODE_STATS] == "not a dict"

    def test_normalize_node_data_not_dict(self):
        """Should skip nodes that are not dicts."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            DocpipeConstants.NODE_STATS: {
                "node-1": "not a dict",
                "node-2": {
                    OperatorConstants.Misc.ID: "node-2",
                    "name": "Node2",
                },
            },
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # node-1 should be unchanged
        assert result[DocpipeConstants.NODE_STATS]["node-1"] == "not a dict"
        # node-2 should be normalized
        assert DocpipeConstants.NODE_ID in result[DocpipeConstants.NODE_STATS]["node-2"]

    def test_normalize_node_with_both_id_and_node_id(self):
        """Should not modify node that has both id and node_id."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            DocpipeConstants.NODE_STATS: {
                "node-1": {
                    OperatorConstants.Misc.ID: "node-1",
                    DocpipeConstants.NODE_ID: "node-1",
                    "name": "TestNode",
                }
            },
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # Should detect new format and not modify
        node_data = result[DocpipeConstants.NODE_STATS]["node-1"]
        assert DocpipeConstants.NODE_ID in node_data
        assert OperatorConstants.Misc.ID in node_data
        assert len(node_data) == 3

    def test_normalize_preserves_other_fields(self):
        """Should preserve all other fields in job_stats_data."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            "status": "COMPLETED",
            "message": "Test message",
            "custom_field": "custom_value",
            DocpipeConstants.NODE_STATS: {
                "node-1": {
                    OperatorConstants.Misc.ID: "node-1",
                    "name": "TestNode",
                }
            },
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # All other fields should be preserved
        assert result["job_id"] == "job-123"
        assert result["job_run_id"] == "run-456"
        assert result["status"] == "COMPLETED"
        assert result["message"] == "Test message"
        assert result["custom_field"] == "custom_value"

    def test_normalize_mixed_format_nodes(self):
        """Should handle mix of old and new format nodes."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            DocpipeConstants.NODE_STATS: {
                "node-1": {
                    DocpipeConstants.NODE_ID: "node-1",  # New format
                    "name": "Node1",
                },
                "node-2": {
                    OperatorConstants.Misc.ID: "node-2",  # Old format
                    "name": "Node2",
                },
            },
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # First node detected as new format, so no normalization happens
        # This is by design - if first node is new format, assume all are
        node1 = result[DocpipeConstants.NODE_STATS]["node-1"]
        assert DocpipeConstants.NODE_ID in node1

        # node-2 won't be normalized because first node was new format
        node2 = result[DocpipeConstants.NODE_STATS]["node-2"]
        assert OperatorConstants.Misc.ID in node2

    def test_normalize_returns_same_dict_reference(self):
        """Should modify and return the same dict reference."""
        job_stats_data = {
            "job_id": "job-123",
            "job_run_id": "run-456",
            DocpipeConstants.NODE_STATS: {
                "node-1": {
                    OperatorConstants.Misc.ID: "node-1",
                    "name": "TestNode",
                }
            },
        }

        result = normalize_node_stats_for_dto(job_stats_data=job_stats_data)

        # Should return the same dict reference
        assert result is job_stats_data
