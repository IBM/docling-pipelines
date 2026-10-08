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
    def derive_ingest_dataset_name(*, ingest_operator: dict[str, Any]) -> str:
        """Derive a human-readable dataset name from the ingest operator config.

        Produces names like ``filesystem://tests/fixtures`` or ``s3://my-bucket``
        so the lineage graph shows a meaningful source rather than a UUID.
        """
        from docpipe.core.constants.operator_constants import OperatorConstants

        operator_config = ingest_operator.get(OperatorConstants.Config.CONFIG, {})
        provider = operator_config.get(OperatorConstants.Config.PROVIDER, "unknown")
        connection_params = operator_config.get(OperatorConstants.Config.CONNECTION_PARAMS, {})
        paths: list[str] = connection_params.get("paths", [])
        if paths:
            first_path = str(paths[0]).rstrip("/")
            return f"{provider}://{first_path}"
        return f"{provider}://source"
