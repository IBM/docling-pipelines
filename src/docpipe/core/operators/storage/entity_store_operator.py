"""Entity storage operator."""

import json

import pyarrow as pa

from docpipe.core.constants.constants import ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.storage.factory import StorageFactory
from docpipe.storage.interfaces.table_storage_port import TableStoragePort
from docpipe.types import FlowConfig, OperatorMetadata, OperatorOutputMetadata, TransformResult


class EntityStoreOperator(AbstractOperator):
    """Store curated entities in DuckDB or PostgreSQL."""

    short_name = OperatorConstants.Operators.ENTITY_STORE_OPERATOR
    category = OperatorCategory.Storage
    owner = "docpipe"

    _SUPPORTED_BACKENDS = ("duckdb", "postgres")

    def __init__(self, config: FlowConfig) -> None:
        super().__init__(config)

        self.data_backend = config.get(
            OperatorConstants.DocumentSet.DATA_BACKEND,
            OperatorConstants.DocumentSet.DEFAULT_DATA_BACKEND,
        )
        self.database_path = config.get(
            OperatorConstants.DocumentSet.DATABASE_PATH,
            ":memory:",
        )
        self.entities_column = config.get(
            "entities_column",
            OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME,
        )

        if self.data_backend not in self._SUPPORTED_BACKENDS:
            raise ValueError(
                f"Unsupported entity storage backend: '{self.data_backend}'. "
                f"Supported backends: {', '.join(self._SUPPORTED_BACKENDS)}"
            )

        if self.data_backend == "duckdb":
            self.storage: TableStoragePort = StorageFactory.create_table_storage(
                storage_type="duckdb",
                database_path=self.database_path,
            )
        else:
            postgres_config = config.get("postgres", {})
            self.storage = StorageFactory.create_table_storage(
                storage_type="postgres",
                config=postgres_config,
            )

    def transform(self, table: pa.Table, file_name: str | None = None) -> TransformResult:
        """Store curated entities and return the input table unchanged."""
        metadata: OperatorOutputMetadata = self.create_base_metadata(
            total_docs_count=table.num_rows,
        )

        if table.num_rows == 0:
            return [table], metadata

        rows_by_table: dict[str, list[dict]] = {}

        for row in table.to_pylist():
            doc_id = str(row.get("id", ""))
            doc_name = str(row.get("name", doc_id))

            try:
                entities_value = row.get(self.entities_column)

                if not entities_value:
                    self.record_skipped_document(
                        metadata=metadata,
                        doc_id=doc_id,
                        doc_name=doc_name,
                        reason=f"Column '{self.entities_column}' is empty",
                    )
                    continue

                if isinstance(entities_value, str):
                    entities = json.loads(entities_value)
                else:
                    entities = entities_value

                if not isinstance(entities, dict):
                    raise ValueError("Curated entities must be a JSON object")

                for table_name, entity_data in entities.items():
                    if isinstance(entity_data, dict):
                        entity_row = {
                            "id": f"{doc_id}:{table_name}",
                            **entity_data,
                        }
                        rows_by_table.setdefault(table_name, []).append(entity_row)

                    elif isinstance(entity_data, list):
                        for row_index, item in enumerate(entity_data):
                            if not isinstance(item, dict):
                                continue

                            entity_row = {
                                "id": f"{doc_id}:{table_name}:{row_index}",
                                **item,
                            }
                            rows_by_table.setdefault(table_name, []).append(entity_row)

                metadata[Metrics.External.PROCESSED_DOCS] += 1

            except Exception as exc:
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    reason=str(exc),
                )

        for table_name, rows in rows_by_table.items():
            all_fields = list(dict.fromkeys(field for row in rows for field in row))

            normalized_rows = [{field: row.get(field) for field in all_fields} for row in rows]

            entity_table = pa.Table.from_pylist(normalized_rows)

            if not self.storage.table_exists(table_name=table_name):
                self.storage.create_table(
                    table_name=table_name,
                    schema=entity_table.schema,
                )

            self.storage.upsert_data(
                table_name=table_name,
                data=entity_table,
            )

        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_ERRORS
        else:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED

        return [table], metadata

    @staticmethod
    def get_required_features() -> list[str]:
        """Return the curated entity column required by this operator."""
        return [OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME]

    @staticmethod
    def get_static_required_features() -> list[str]:
        """Return required features for operator discovery."""
        return [OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME]

    @staticmethod
    def get_metadata() -> OperatorMetadata:
        """Return metadata describing the entity storage operator."""
        return {
            "short_name": OperatorConstants.Operators.ENTITY_STORE_OPERATOR,
            "description": "Store curated entities in DuckDB or PostgreSQL.",
            "category": OperatorCategory.Storage.value,
            "owner": "docpipe",
            "attributes": {
                "data_backend": {
                    "type": "string",
                    "default": "duckdb",
                    "valid_values": ["duckdb", "postgres"],
                },
                "database_path": {
                    "type": "string",
                    "default": ":memory:",
                },
            },
        }
