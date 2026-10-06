"""Unit tests for LineageUtils."""

import uuid

import pytest

from docpipe.core.lineage.utils import LineageUtils


class TestLineageUtils:
    """Consolidated test suite for LineageUtils static helpers."""

    def test_now_returns_iso_format(self) -> None:
        now_str = LineageUtils.now()
        assert isinstance(now_str, str)
        assert "T" in now_str
        assert "+" in now_str or "Z" in now_str

    def test_is_valid_uuid(self) -> None:
        valid_id = str(uuid.uuid4())
        assert LineageUtils.is_valid_uuid(valid_id) is True
        assert LineageUtils.is_valid_uuid("not-a-uuid") is False
        assert LineageUtils.is_valid_uuid("") is False

    @pytest.mark.parametrize(
        ("snake", "expected"),
        [
            ("processed_docs", "processedDocs"),
            ("docs_before_filter", "docsBeforeFilter"),
            ("chunks_indexed_successfully", "chunksIndexedSuccessfully"),
            ("node_status", "nodeStatus"),
            ("total_chunks_to_index", "totalChunksToIndex"),
            ("nrows", "nrows"),
            ("processedDocs", "processedDocs"),
        ],
    )
    def test_to_camel_case(self, snake: str, expected: str) -> None:
        assert LineageUtils.to_camel_case(snake) == expected

    def test_strip_credentials(self) -> None:
        data = {
            "api_key": "secret123",
            "password": "pass",
            "node": {
                "name": "op1",
                "token": "tok456",
                "safe_config": {"batch_size": 10},
            },
        }
        stripped = LineageUtils.strip_credentials(data)
        assert "api_key" not in stripped
        assert "password" not in stripped
        assert stripped["node"]["name"] == "op1"
        assert "token" not in stripped["node"]
        assert stripped["node"]["safe_config"]["batch_size"] == 10
        assert LineageUtils.strip_credentials("string") == "string"

    def test_node_run_id(self) -> None:
        job_run_id = str(uuid.uuid4())
        node_id = "chunker_node"
        id1 = LineageUtils.node_run_id(job_run_id=job_run_id, node_id=node_id)
        id2 = LineageUtils.node_run_id(job_run_id=job_run_id, node_id=node_id)
        assert id1 == id2
        assert LineageUtils.is_valid_uuid(id1) is True
        # non-UUID job_run_id fallback
        id3 = LineageUtils.node_run_id(job_run_id="custom-run-1", node_id="node-1")
        assert LineageUtils.is_valid_uuid(id3) is True

    def test_resolve_flow_id(self) -> None:
        res = LineageUtils.resolve_flow_id(flow_id="my-flow-id", flow_def={"a": 1})
        assert res == "my-flow-id"
        # empty flow_id falls back to sha256
        res1 = LineageUtils.resolve_flow_id(flow_id="", flow_def={"flow_name": "test"})
        res2 = LineageUtils.resolve_flow_id(flow_id="", flow_def={"flow_name": "test"})
        assert res1 == res2
        assert len(res1) == 64

    def test_derive_ingest_dataset_name(self) -> None:
        op_with_paths = {
            "config": {
                "provider": "filesystem",
                "connection_params": {"paths": ["./tests/fixtures/customer_support_docs/"]},
            }
        }
        assert (
            LineageUtils.derive_ingest_dataset_name(ingest_operator=op_with_paths)
            == "filesystem://./tests/fixtures/customer_support_docs"
        )
        assert LineageUtils.derive_ingest_dataset_name(ingest_operator={"config": {"provider": "s3"}}) == "s3://source"
        assert LineageUtils.derive_ingest_dataset_name(ingest_operator={}) == "unknown://source"
