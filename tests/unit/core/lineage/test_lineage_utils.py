"""Unit tests for LineageUtils."""

import uuid
from typing import Any

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
            "api_key": "secret123",  # pragma: allowlist secret
            "password": "pass",  # pragma: allowlist secret
            "node": {
                "name": "op1",
                "token": "tok456",  # pragma: allowlist secret
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
        list_data = [{"api_key": "secret", "value": 1}, {"safe": 2}]  # pragma: allowlist secret
        stripped_list = LineageUtils.strip_credentials(list_data)
        assert stripped_list == [{"value": 1}, {"safe": 2}]

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

    def test_derive_dataset_info_from_ingest(self) -> None:
        fs_op = {
            "config": {
                "provider": "filesystem",
                "connection_params": {"paths": ["./tests/fixtures/customer_support_docs/"]},
            }
        }
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=fs_op) == (
            "file",
            "./tests/fixtures/customer_support_docs",
        )

        s3_op = {
            "config": {
                "provider": "s3",
                "provider_config": {"bucket": "my-bucket", "prefix": "data/docs"},
            }
        }
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=s3_op) == (
            "s3://my-bucket",
            "data/docs",
        )

        empty_op: dict[str, Any] = {}
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=empty_op) == (
            "unknown://source",
            "source",
        )

        # Single path in provider_config & operator_config
        single_path_op = {
            "config": {
                "provider": "local",
                "provider_config": {"path": "/var/data"},
            }
        }
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=single_path_op) == (
            "file",
            "/var/data",
        )

        op_cfg_path_op = {
            "config": {
                "provider": "file",
                "path": "/opt/data",
            }
        }
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=op_cfg_path_op) == (
            "file",
            "/opt/data",
        )

        fs_no_paths = {"config": {"provider": "filesystem"}}
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=fs_no_paths) == (
            "file",
            "source",
        )

        # S3 defaults
        s3_default_op = {"config": {"provider": "s3"}}
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=s3_default_op) == (
            "s3://source-bucket",
            "/",
        )

        # Box provider
        box_op = {
            "config": {
                "provider": "box",
                "provider_config": {
                    "enterprise_id": "ent_123",
                    "host": "custom.box.com",
                    "port": 8443,
                    "path": "/shared/docs",
                },
            }
        }
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=box_op) == (
            "box://custom.box.com:8443/ent_123",
            "/shared/docs",
        )

        box_default_op = {"config": {"provider": "box"}}
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=box_default_op) == (
            "box://app.box.com:443/default",
            "root",
        )

        # SharePoint provider
        sp_op = {
            "config": {
                "provider": "sharepoint",
                "provider_config": {
                    "site": "engineering",
                    "host": "myorg.sharepoint.com",
                    "port": 443,
                    "path": "shared_docs",
                },
            }
        }
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=sp_op) == (
            "mssharepoint://myorg.sharepoint.com:443/engineering",
            "shared_docs",
        )

        sp_default_op = {"config": {"provider": "sharepoint"}}
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=sp_default_op) == (
            "mssharepoint://sharepoint.com:443/default",
            "documents",
        )

        # Google Drive provider
        gdrive_op = {
            "config": {
                "provider": "google_drive",
                "provider_config": {"path": "my_folder"},
            }
        }
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=gdrive_op) == (
            "googledrive://drive.google.com",
            "my_folder",
        )

        gdrive_default_op = {"config": {"provider": "google_drive"}}
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=gdrive_default_op) == (
            "googledrive://drive.google.com",
            "root",
        )

        # Custom provider with paths
        custom_op = {
            "config": {
                "provider": "azure_blob",
                "connection_params": {"paths": ["container/data"]},
            }
        }
        assert LineageUtils.derive_dataset_info_from_ingest(ingest_operator=custom_op) == (
            "azure_blob://source",
            "container/data",
        )

    def test_derive_dataset_info_from_sink(self) -> None:
        opensearch_op = {
            "type": "vectordb",
            "config": {
                "provider": "opensearch",
                "provider_config": {"host": "localhost", "port": 9200, "index_name": "kb_index"},
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=opensearch_op) == (
            "opensearch://localhost:9200",
            "kb_index",
        )

        milvus_op = {
            "type": "vectordb",
            "config": {
                "provider": "milvus",
                "provider_config": {
                    "host": "milvus.local",
                    "port": 19530,
                    "database": "kb_db",
                    "collection_name": "chunks",
                },
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=milvus_op) == (
            "milvus://milvus.local:19530",
            "kb_db.chunks",
        )

        storage_s3_op = {
            "type": "storage_output",
            "config": {
                "destination_config": {
                    "provider": "s3",
                    "provider_config": {"bucket": "out-bucket", "prefix": "processed"},
                }
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=storage_s3_op) == (
            "s3://out-bucket",
            "processed",
        )

        storage_fs_op = {
            "type": "storage_output",
            "config": {
                "destination_config": {
                    "provider": "filesystem",
                    "provider_config": {"paths": ["/tmp/out"]},
                }
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=storage_fs_op) == (
            "file",
            "/tmp/out",
        )

        docset_op = {
            "type": "document_set",
            "config": {"document_set_name": "my_dataset"},
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=docset_op) == (
            "docpipe://document_set",
            "my_dataset",
        )

        chunker_op = {
            "type": "chunker",
            "config": {},
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=chunker_op) is None

        # Milvus with default database & collection
        milvus_def_op = {
            "type": "vectordb",
            "config": {"provider": "milvus"},
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=milvus_def_op) == (
            "milvus://localhost:19530",
            "default.default_collection",
        )

        # Opensearch with config root fallback
        opensearch_fallback = {
            "type": "vector_db",
            "config": {"provider": "opensearch", "index_name": "direct_kb"},
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=opensearch_fallback) == (
            "opensearch://localhost:9200",
            "direct_kb",
        )

        # Generic vector provider (e.g. Qdrant) with port and without port
        qdrant_op = {
            "type": "vectordb",
            "config": {
                "provider": "qdrant",
                "provider_config": {"host": "qdrant.internal", "port": 6333, "collection_name": "docs"},
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=qdrant_op) == (
            "qdrant://qdrant.internal:6333",
            "docs",
        )

        qdrant_no_port = {
            "type": "VectorDBOperator",
            "config": {
                "provider": "qdrant",
                "provider_config": {"host": "qdrant.internal", "index_name": "idx"},
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=qdrant_no_port) == (
            "qdrant://qdrant.internal",
            "idx",
        )

        # Storage sinks: Box, SharePoint, Google Drive, generic
        storage_box_op = {
            "type": "storage_output",
            "config": {
                "destination_config": {
                    "provider": "box",
                    "provider_config": {
                        "enterprise_id": "box_ent",
                        "host": "box.corp.com",
                        "port": 443,
                        "path": "/out",
                    },
                }
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=storage_box_op) == (
            "box://box.corp.com:443/box_ent",
            "/out",
        )

        storage_sp_op = {
            "type": "StorageOutputOperator",
            "config": {
                "destination_config": {
                    "provider": "sharepoint",
                    "provider_config": {
                        "site": "sales",
                        "host": "sharepoint.corp.com",
                        "port": 443,
                        "path": "exports",
                    },
                }
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=storage_sp_op) == (
            "mssharepoint://sharepoint.corp.com:443/sales",
            "exports",
        )

        storage_gdrive_op = {
            "type": "storage",
            "config": {
                "destination_config": {
                    "provider": "google_drive",
                    "provider_config": {"path": "target_folder"},
                }
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=storage_gdrive_op) == (
            "googledrive://drive.google.com",
            "target_folder",
        )

        storage_custom_op = {
            "type": "storage_output",
            "config": {
                "destination_config": {
                    "provider": "custom_store",
                }
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=storage_custom_op) == (
            "custom_store://destination",
            "output",
        )

        # Storage local with single path and base_path
        storage_local_single = {
            "type": "storage_output",
            "config": {
                "destination_config": {
                    "provider": "local",
                    "provider_config": {"path": "/tmp/local_out"},
                }
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=storage_local_single) == (
            "file",
            "/tmp/local_out",
        )

        storage_file_base = {
            "type": "storage_output",
            "config": {
                "destination_config": {
                    "provider": "file",
                    "provider_config": {"base_path": "/tmp/base_out"},
                }
            },
        }
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=storage_file_base) == (
            "file",
            "/tmp/base_out",
        )

        # Document set default name
        docset_default = {"type": "DocumentSetOperator", "config": {}}
        assert LineageUtils.derive_dataset_info_from_sink(operator_def=docset_default) == (
            "docpipe://document_set",
            "document_set",
        )

    def test_derive_ingest_dataset_name(self) -> None:
        ingest_op = {
            "config": {
                "provider": "filesystem",
                "connection_params": {"paths": ["/data/input/"]},
            }
        }
        assert LineageUtils.derive_ingest_dataset_name(ingest_operator=ingest_op) == "/data/input"

        op_with_paths = {
            "config": {
                "provider": "filesystem",
                "connection_params": {"paths": ["./tests/fixtures/customer_support_docs/"]},
            }
        }
        assert (
            LineageUtils.derive_ingest_dataset_name(ingest_operator=op_with_paths)
            == "./tests/fixtures/customer_support_docs"
        )
