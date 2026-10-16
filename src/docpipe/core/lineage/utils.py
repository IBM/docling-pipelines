"""Utility functions and helpers for OpenLineage integration."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

_CREDENTIALS_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "secret",
        "secret_key",
        "password",
        "token",
        "auth_token",
        "access_token",
        "credentials",
        "connection_params",
    }
)


class LineageUtils:
    """Utility class providing static helper methods for lineage data transformation and validation."""

    @staticmethod
    def now() -> str:
        """Return current timestamp in ISO-8601 format with UTC timezone."""
        return datetime.now(tz=UTC).isoformat()

    @staticmethod
    def is_valid_uuid(value: str) -> bool:
        """Check whether a string is a valid UUID."""
        try:
            uuid.UUID(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def to_camel_case(snake: str) -> str:
        """Convert ``snake_case`` to ``camelCase`` for facet field names.

        Examples::

            "processed_docs"          -> "processedDocs"
            "docs_before_filter"      -> "docsBeforeFilter"
            "chunks_indexed_successfully" -> "chunksIndexedSuccessfully"
            "node_status"             -> "nodeStatus"
            "nrows"                   -> "nrows"   (single word, unchanged)
        """
        parts = snake.split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])

    @staticmethod
    def strip_credentials(flow_def: Any) -> Any:
        """Recursively remove credential keys from a flow definition dict or list."""
        if isinstance(flow_def, dict):
            return {
                k: LineageUtils.strip_credentials(v) for k, v in flow_def.items() if k.lower() not in _CREDENTIALS_KEYS
            }
        if isinstance(flow_def, list):
            return [LineageUtils.strip_credentials(item) for item in flow_def]
        return flow_def

    @staticmethod
    def node_run_id(*, job_run_id: str, node_id: str) -> str:
        """Derive a deterministic UUID for a node run from the job run ID and node ID."""
        return str(
            uuid.uuid5(
                uuid.UUID(job_run_id) if LineageUtils.is_valid_uuid(job_run_id) else uuid.NAMESPACE_URL,
                node_id,
            )
        )

    @staticmethod
    def resolve_flow_id(*, flow_id: str, flow_def: dict[str, Any]) -> str:
        """Use flow_id directly; fall back to SHA-256 of credentials-stripped flow_def."""
        if flow_id:
            return flow_id
        stripped = LineageUtils.strip_credentials(flow_def)
        return hashlib.sha256(json.dumps(stripped, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def derive_dataset_info_from_ingest(*, ingest_operator: dict[str, Any]) -> tuple[str, str]:
        """Derive standard OpenLineage (namespace, name) tuple from ingest operator config.

        Follows OpenLineage naming specifications:
        - Local file system -> namespace: "file", name: "{path}"
        - S3 -> namespace: "s3://{bucket}", name: "{prefix}"
        - Box -> namespace: "box://{host}:{port}/{enterprise_id}", name: "{path}"
        - SharePoint -> namespace: "mssharepoint://{host}:{port}/{site}", name: "{path}"
        """
        from docpipe.core.constants.constants import LineageConstants
        from docpipe.core.constants.operator_constants import OperatorConstants

        operator_config = ingest_operator.get(OperatorConstants.Config.CONFIG, {})
        provider = operator_config.get(OperatorConstants.Config.PROVIDER, "unknown")
        provider_config = operator_config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})
        connection_params = operator_config.get(OperatorConstants.Config.CONNECTION_PARAMS, {})

        paths: list[str] = (
            connection_params.get("paths") or provider_config.get("paths") or operator_config.get("paths") or []
        )
        if not paths and "path" in provider_config:
            paths = [provider_config["path"]]
        if not paths and "path" in operator_config:
            paths = [operator_config["path"]]

        if provider in (
            LineageConstants.PROVIDER_FILESYSTEM,
            LineageConstants.PROVIDER_LOCAL,
            LineageConstants.PROVIDER_FILE,
        ):
            name = str(paths[0]).rstrip("/") if paths else "source"
            return (LineageConstants.NAMESPACE_FILE, name)

        if provider == LineageConstants.PROVIDER_S3:
            bucket = (
                provider_config.get("bucket")
                or connection_params.get("bucket")
                or operator_config.get("bucket")
                or "source-bucket"
            )
            prefix = (
                provider_config.get("prefix") or connection_params.get("prefix") or operator_config.get("prefix") or ""
            )
            name = str(prefix).rstrip("/") if prefix else "/"
            return (f"s3://{bucket}", name)

        if provider == LineageConstants.PROVIDER_BOX:
            enterprise_id = provider_config.get("enterprise_id") or operator_config.get("enterprise_id") or "default"
            host = provider_config.get("host") or operator_config.get("host") or "app.box.com"
            port = provider_config.get("port") or operator_config.get("port") or 443
            path = provider_config.get("path") or operator_config.get("path") or "root"
            return (f"box://{host}:{port}/{enterprise_id}", str(path))

        if provider == LineageConstants.PROVIDER_SHAREPOINT:
            site = provider_config.get("site") or operator_config.get("site") or "default"
            host = provider_config.get("host") or operator_config.get("host") or "sharepoint.com"
            port = provider_config.get("port") or operator_config.get("port") or 443
            path = provider_config.get("path") or operator_config.get("path") or "documents"
            return (f"mssharepoint://{host}:{port}/{site}", str(path))

        if provider == LineageConstants.PROVIDER_GOOGLE_DRIVE:
            path = provider_config.get("path") or operator_config.get("path") or "root"
            return (LineageConstants.NAMESPACE_GOOGLE_DRIVE, str(path))

        name = str(paths[0]).rstrip("/") if paths else "source"
        return (f"{provider}://source", name)

    @staticmethod
    def derive_dataset_info_from_sink(*, operator_def: dict[str, Any]) -> tuple[str, str] | None:
        """Derive standard OpenLineage (namespace, name) tuple from a sink operator definition.

        Returns None if the operator is not a known data sink (e.g. intermediate transformation).
        """
        from docpipe.core.constants.constants import LineageConstants
        from docpipe.core.constants.operator_constants import OperatorConstants

        operator_type = operator_def.get(OperatorConstants.Misc.OPERATOR) or operator_def.get("type", "")
        config = operator_def.get(OperatorConstants.Config.CONFIG, {})

        if operator_type in (
            OperatorConstants.Operators.VECTORDB,
            "vector_db",
            "VectorDBOperator",
        ) or config.get(OperatorConstants.Config.PROVIDER) in (
            LineageConstants.PROVIDER_OPENSEARCH,
            LineageConstants.PROVIDER_MILVUS,
            LineageConstants.PROVIDER_QDRANT,
            LineageConstants.PROVIDER_WEAVIATE,
            LineageConstants.PROVIDER_PINECONE,
            LineageConstants.PROVIDER_CHROMA,
        ):
            provider = config.get(OperatorConstants.Config.PROVIDER, LineageConstants.PROVIDER_OPENSEARCH)
            p_cfg = config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})
            if provider == LineageConstants.PROVIDER_OPENSEARCH:
                host = p_cfg.get("host") or config.get("host", "localhost")
                port = p_cfg.get("port") or config.get("port", 9200)
                index_name = p_cfg.get("index_name") or config.get("index_name", "default_index")
                return (f"opensearch://{host}:{port}", str(index_name))
            if provider == LineageConstants.PROVIDER_MILVUS:
                host = p_cfg.get("host") or config.get("host", "localhost")
                port = p_cfg.get("port") or config.get("port", 19530)
                database = p_cfg.get("database") or config.get("database", "default")
                collection = (
                    p_cfg.get("collection_name")
                    or p_cfg.get("index_name")
                    or config.get("collection_name")
                    or config.get("index_name", "default_collection")
                )
                return (f"milvus://{host}:{port}", f"{database}.{collection}")
            host = p_cfg.get("host") or config.get("host", "localhost")
            port = p_cfg.get("port") or config.get("port", "")
            port_suffix = f":{port}" if port else ""
            target = (
                p_cfg.get("index_name")
                or config.get("index_name")
                or p_cfg.get("collection_name")
                or config.get("collection_name", "sink")
            )
            return (f"{provider}://{host}{port_suffix}", str(target))

        if (
            operator_type
            in (
                OperatorConstants.Operators.STORAGE_OUTPUT,
                "storage",
                "StorageOutputOperator",
            )
            or "destination_config" in config
        ):
            dest_cfg = config.get("destination_config", {})
            provider = dest_cfg.get(OperatorConstants.Config.PROVIDER, LineageConstants.PROVIDER_FILESYSTEM)
            p_cfg = dest_cfg.get(OperatorConstants.Config.PROVIDER_CONFIG, {})
            if provider in (
                LineageConstants.PROVIDER_FILESYSTEM,
                LineageConstants.PROVIDER_LOCAL,
                LineageConstants.PROVIDER_FILE,
            ):
                paths = p_cfg.get("paths") or [p_cfg.get("path") or p_cfg.get("base_path", "output")]
                return (LineageConstants.NAMESPACE_FILE, str(paths[0]))
            if provider == LineageConstants.PROVIDER_S3:
                bucket = p_cfg.get("bucket", "output-bucket")
                prefix = p_cfg.get("prefix", "exports")
                return (f"s3://{bucket}", str(prefix))
            if provider == LineageConstants.PROVIDER_BOX:
                enterprise_id = p_cfg.get("enterprise_id", "default")
                host = p_cfg.get("host", "app.box.com")
                port = p_cfg.get("port", 443)
                path = p_cfg.get("path", "root")
                return (f"box://{host}:{port}/{enterprise_id}", str(path))
            if provider == LineageConstants.PROVIDER_SHAREPOINT:
                site = p_cfg.get("site", "default")
                host = p_cfg.get("host", "sharepoint.com")
                port = p_cfg.get("port", 443)
                path = p_cfg.get("path", "documents")
                return (f"mssharepoint://{host}:{port}/{site}", str(path))
            if provider == LineageConstants.PROVIDER_GOOGLE_DRIVE:
                path = p_cfg.get("path", "root")
                return (LineageConstants.NAMESPACE_GOOGLE_DRIVE, str(path))
            return (f"{provider}://destination", "output")

        if operator_type in (
            OperatorConstants.Operators.DOCUMENT_SET,
            "document_set_operator",
            "DocumentSetOperator",
        ):
            doc_set_name = config.get("document_set_name", "document_set")
            return (LineageConstants.NAMESPACE_DOCUMENT_SET, str(doc_set_name))

        return None

    @staticmethod
    def derive_ingest_dataset_name(*, ingest_operator: dict[str, Any]) -> str:
        """Derive a human-readable dataset name from the ingest operator config.

        Produces names like ``tests/fixtures`` or ``my-bucket``
        so the lineage graph shows a meaningful source rather than a UUID.
        """
        _, name = LineageUtils.derive_dataset_info_from_ingest(ingest_operator=ingest_operator)
        return name
