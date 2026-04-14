#!/usr/bin/env python3
"""
OpenSearch Batch Processor
Handles bulk operations including indexing, updates, and deletes with batching logic.
"""

import json
from typing import Any

from opensearchpy import OpenSearch, helpers

from common.util.infrastructure.logging import get_logger

logger = get_logger()


# Batch processing constants
DEFAULT_BATCH_SIZE: int = 100
MAX_BATCH_SIZE_MB: int = 3  # Maximum batch size in MB
BULK_INSERT_TIMEOUT: int = 180  # 3 minutes timeout
BULK_DELETE_BATCH_SIZE: int = 500


class OpenSearchBatchProcessor:
    """
    Manages batch operations for OpenSearch including bulk indexing and deletes.

    Responsibilities:
    - Size-aware batch processing
    - Bulk indexing with error tracking
    - Bulk delete operations
    - Document preparation and validation
    - Query operations
    """

    def __init__(
        self,
        client: OpenSearch,
        index_name: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        available_features: dict[str, Any] | None = None,
        feature_mappings: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize the batch processor.

        Args:
            client: OpenSearch client instance
            index_name: Name of the index
            batch_size: Maximum documents per batch
            available_features: Feature configuration
            feature_mappings: Column to field mappings
        """
        self.client = client
        self.index_name = index_name
        self.batch_size = batch_size
        self.available_features = available_features or {}
        self.feature_mappings = feature_mappings or {}

    def prepare_document(self, row_data: dict[str, Any]) -> dict[str, Any]:
        """
        Prepare a document for indexing by mapping columns to index fields.

        Args:
            row_data: Raw row data from PyArrow table

        Returns:
            Prepared document ready for indexing
        """
        doc: dict[str, Any] = {}

        for feature_name, feature_config in self.available_features.items():
            if not feature_config.get("available_for_vector_db", False):
                continue

            mapped_name: str = self.feature_mappings.get(feature_name, feature_name)

            if feature_name in row_data:
                value: Any = row_data[feature_name]

                if value is None:
                    continue

                # Convert numpy arrays to lists
                if hasattr(value, "tolist"):
                    value = value.tolist()

                # Parse JSON strings for object/nested types
                feature_type: str = feature_config.get("type", "text")
                if feature_type in ("object", "nested", "json") and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, keep as string
                        pass

                doc[mapped_name] = value

        return doc

    def calculate_batch_size_bytes(self, documents: list[dict[str, Any]]) -> int:
        """
        Calculate approximate size of documents in bytes.

        Args:
            documents: List of documents

        Returns:
            Size in bytes
        """
        try:
            return len(json.dumps(documents).encode("utf-8"))
        except Exception:
            return 0

    def bulk_index(self, actions: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
        """
        Perform bulk indexing operation.

        Args:
            actions: List of bulk actions

        Returns:
            Tuple of (success_count, failed_items)
        """
        try:
            success: int
            failed: list[dict[str, Any]]
            success, failed = helpers.bulk(
                self.client,
                actions,
                raise_on_error=False,
                raise_on_exception=False,
                request_timeout=BULK_INSERT_TIMEOUT,
            )
            return success, failed
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e!s}")
            return 0, actions

    def process_batches(self, all_actions: list[list[dict[str, Any]]]) -> tuple[int, list[dict[str, Any]]]:
        """
        Process multiple batches of actions.

        Args:
            all_actions: List of batches, where each batch is a list of actions

        Returns:
            Tuple of (total_success_count, all_failed_items)
        """
        success_count: int = 0
        all_failed: list[dict[str, Any]] = []

        for batch_idx, batch in enumerate(all_actions):
            try:
                logger.info(f"Processing batch {batch_idx + 1}/{len(all_actions)} with {len(batch)} documents")

                success: int
                failed: list[dict[str, Any]]
                success, failed = self.bulk_index(batch)
                success_count += success

                if failed:
                    all_failed.extend(failed)

            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} indexing failed: {e!s}")
                all_failed.extend(batch)

        logger.info(f"Successfully indexed {success_count} documents in {len(all_actions)} batches")
        return success_count, all_failed

    def create_batches(self, documents: list[tuple[str, dict[str, Any]]]) -> list[list[dict[str, Any]]]:
        """
        Create size-aware batches from documents.

        Args:
            documents: List of (doc_id, document) tuples

        Returns:
            List of batches, where each batch is a list of actions
        """
        all_actions: list[list[dict[str, Any]]] = []
        current_batch: list[dict[str, Any]] = []
        current_batch_size: int = 0
        max_batch_size_bytes: int = MAX_BATCH_SIZE_MB * 1024 * 1024

        for doc_id, doc in documents:
            prepared_doc = self.prepare_document(doc)

            action: dict[str, Any] = {
                "_index": self.index_name,
                "_id": doc_id,
                "_source": prepared_doc,
            }

            # Check batch size
            action_size: int = self.calculate_batch_size_bytes([action])
            if current_batch and (
                current_batch_size + action_size > max_batch_size_bytes or len(current_batch) >= self.batch_size
            ):
                all_actions.append(current_batch)
                current_batch = []
                current_batch_size = 0

            current_batch.append(action)
            current_batch_size += action_size

        # Add remaining batch
        if current_batch:
            all_actions.append(current_batch)

        return all_actions

    def query_by_doc_names(self, doc_names: list[str], fields: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Query documents by their names.

        Args:
            doc_names: List of document names to query
            fields: Optional list of fields to return

        Returns:
            List of matching documents
        """
        if not doc_names:
            return []

        try:
            # Build query
            query: dict[str, Any] = {
                "query": {"terms": {"name.keyword": doc_names}},
                "size": len(doc_names),
            }

            if fields:
                query["_source"] = fields

            response: dict[str, Any] = self.client.search(index=self.index_name, body=query)
            hits: list[dict[str, Any]] = response.get("hits", {}).get("hits", [])

            return [hit["_source"] for hit in hits]

        except Exception as e:
            logger.error(f"Error querying documents: {e!s}")
            return []

    def delete_documents_by_ids(self, doc_ids: list[str]) -> tuple[int, int]:
        """
        Delete documents by their IDs.

        Args:
            doc_ids: List of document IDs to delete

        Returns:
            Tuple of (success_count, failed_count)
        """
        if not doc_ids:
            return 0, 0

        success_count: int = 0
        failed_count: int = 0

        try:
            # Process in batches
            for i in range(0, len(doc_ids), BULK_DELETE_BATCH_SIZE):
                batch: list[str] = doc_ids[i : i + BULK_DELETE_BATCH_SIZE]

                # Build bulk delete actions
                actions: list[dict[str, Any]] = [
                    {"_op_type": "delete", "_index": self.index_name, "_id": doc_id} for doc_id in batch
                ]

                success: int
                failed: list[dict[str, Any]]
                success, failed = helpers.bulk(self.client, actions, raise_on_error=False, raise_on_exception=False)

                success_count += success
                failed_count += len(failed)

            logger.info(f"Deleted {success_count} documents, {failed_count} failed")

        except Exception as e:
            logger.error(f"Error deleting documents: {e!s}")
            failed_count = len(doc_ids)

        return success_count, failed_count

    def get_document_count(self) -> int:
        """
        Get total document count in the index.

        Returns:
            Number of documents in the index
        """
        try:
            response: dict[str, Any] = self.client.count(index=self.index_name)
            return response.get("count", 0)
        except Exception as e:
            logger.error(f"Error getting document count: {e!s}")
            return 0
