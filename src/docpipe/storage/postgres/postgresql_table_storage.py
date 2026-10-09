"""PostgreSQL storage implementation for PyArrow tables."""

import re
from collections.abc import Mapping
from typing import Any

import pyarrow as pa
from sqlalchemy import text

from docpipe.core.job_management.adapters.stores.postgres.database import (
    create_postgres_engine,
    get_postgres_connection_string,
)
from docpipe.storage.exceptions import StorageConnectionError, StorageException, StorageValidationError
from docpipe.storage.interfaces.table_storage_port import TableStoragePort
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)

_IDENTIFIER_RE = re.compile(r"^\w+$")

_PYARROW_TO_POSTGRES: list[tuple[Any, str]] = [
    (pa.types.is_string, "TEXT"),
    (pa.types.is_large_string, "TEXT"),
    (pa.types.is_int64, "BIGINT"),
    (pa.types.is_int32, "INTEGER"),
    (pa.types.is_int16, "SMALLINT"),
    (pa.types.is_int8, "SMALLINT"),
    (pa.types.is_float64, "DOUBLE PRECISION"),
    (pa.types.is_float32, "REAL"),
    (pa.types.is_boolean, "BOOLEAN"),
    (pa.types.is_binary, "BYTEA"),
    (pa.types.is_large_binary, "BYTEA"),
    (pa.types.is_timestamp, "TIMESTAMP"),
    (pa.types.is_date, "DATE"),
    (pa.types.is_time, "TIME"),
]


class PostgreSQLTableStorage(TableStoragePort):
    """PostgreSQL implementation of PyArrow table storage."""

    def __init__(self, *, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

        connection_string = get_postgres_connection_string(config={"postgres": self.config})
        if not connection_string:
            raise StorageConnectionError(
                message=(
                    "PostgreSQL connection is not configured. Set password in config or DOCPIPE_POSTGRES_PASSWORD."
                )
            )

        try:
            self.engine = create_postgres_engine(
                connection_string=connection_string,
                config={"postgres": self.config},
            )
        except Exception as exc:
            raise StorageConnectionError(message=f"Failed to initialize PostgreSQL storage: {exc}") from exc

        logger.info("Initialized PostgreSQLTableStorage")

    def _validate_identifier(self, *, identifier: str, kind: str) -> None:
        if not identifier or not isinstance(identifier, str):
            raise StorageValidationError(message=f"{kind} cannot be empty")

        if not _IDENTIFIER_RE.match(identifier):
            raise StorageValidationError(
                message=(f"Invalid {kind}: {identifier}. Must contain only alphanumeric characters and underscores.")
            )

    def _quote_identifier(self, *, identifier: str) -> str:
        return f'"{identifier}"'

    def _pyarrow_to_postgres_type(self, *, pa_type: pa.DataType) -> str:
        for type_check, postgres_type in _PYARROW_TO_POSTGRES:
            if type_check(pa_type):
                return postgres_type

        if pa.types.is_list(pa_type) or pa.types.is_large_list(pa_type):
            return "JSONB"

        if pa.types.is_struct(pa_type) or pa.types.is_map(pa_type):
            return "JSONB"

        logger.warning("Unknown PyArrow type %s, defaulting to TEXT", pa_type)
        return "TEXT"

    def create_table(self, *, table_name: str, schema: pa.Schema) -> None:
        self._validate_identifier(identifier=table_name, kind="table name")

        try:
            columns = []

            for field in schema:
                self._validate_identifier(identifier=field.name, kind="column name")

                column_type = self._pyarrow_to_postgres_type(pa_type=field.type)
                quoted_column = self._quote_identifier(identifier=field.name)

                if field.name == "id":
                    columns.append(f"{quoted_column} {column_type} PRIMARY KEY")
                else:
                    columns.append(f"{quoted_column} {column_type}")

            quoted_table = self._quote_identifier(identifier=table_name)

            query = f"""
                CREATE TABLE IF NOT EXISTS {quoted_table} (
                    {", ".join(columns)}
                )
            """  # nosec B608 — identifiers are validated and quoted.

            with self.engine.begin() as connection:
                connection.execute(text(query))

            logger.info("Created PostgreSQL table: %s", table_name)

        except StorageException:
            raise
        except Exception as exc:
            raise StorageException(message=f"Failed to create table {table_name}: {exc}") from exc

    def _handle_schema_evolution(self, *, table_name: str, new_schema: pa.Schema) -> None:
        """Add columns that are present in the new schema but missing from the table."""
        current_columns_query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = :table_name
        """

        try:
            with self.engine.begin() as connection:
                result = connection.execute(
                    text(current_columns_query),
                    {"table_name": table_name},
                )
                current_columns = {row["column_name"] for row in result.mappings().all()}

                columns_to_add = set(new_schema.names) - current_columns

                quoted_table = self._quote_identifier(identifier=table_name)

                for column_name in columns_to_add:
                    self._validate_identifier(
                        identifier=column_name,
                        kind="column name",
                    )

                    field = new_schema.field(column_name)
                    postgres_type = self._pyarrow_to_postgres_type(
                        pa_type=field.type,
                    )
                    quoted_column = self._quote_identifier(identifier=column_name)

                    alter_sql = f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {postgres_type}"
                    connection.execute(text(alter_sql))
                    logger.info(
                        "Added column %s to PostgreSQL table %s",
                        column_name,
                        table_name,
                    )

        except StorageException:
            raise
        except Exception as exc:
            raise StorageException(message=f"Failed to evolve schema for {table_name}: {exc}") from exc

    def upsert_data(self, *, table_name: str, data: pa.Table) -> None:
        self._validate_identifier(identifier=table_name, kind="table name")

        if not self.table_exists(table_name=table_name):
            raise StorageException(message=f"Table {table_name} does not exist")

        if "id" not in data.schema.names:
            raise StorageValidationError(message="Data must contain an 'id' column for upsert")

        if data.num_rows == 0:
            return

        try:
            self._handle_schema_evolution(
                table_name=table_name,
                new_schema=data.schema,
            )

            columns = list(data.schema.names)

            for column in columns:
                self._validate_identifier(identifier=column, kind="column name")

            quoted_table = self._quote_identifier(identifier=table_name)
            quoted_columns = [self._quote_identifier(identifier=column) for column in columns]

            column_names = ", ".join(quoted_columns)
            placeholders = ", ".join(f":{column}" for column in columns)

            update_columns = [column for column in columns if column != "id"]

            if update_columns:
                update_clause = ", ".join(
                    f"{self._quote_identifier(identifier=column)} = EXCLUDED.{self._quote_identifier(identifier=column)}"
                    for column in update_columns
                )

                query = f"""
                    INSERT INTO {quoted_table} ({column_names})
                    VALUES ({placeholders})
                    ON CONFLICT ("id") DO UPDATE SET
                        {update_clause}
                """  # nosec B608 — identifiers are validated and quoted.
            else:
                query = f"""
                    INSERT INTO {quoted_table} ({column_names})
                    VALUES ({placeholders})
                    ON CONFLICT ("id") DO NOTHING
                """  # nosec B608 — identifiers are validated and quoted.

            rows = data.to_pylist()

            with self.engine.begin() as connection:
                for row in rows:
                    connection.execute(text(query), row)

            logger.debug("Upserted %s rows into PostgreSQL table %s", len(rows), table_name)

        except StorageException:
            raise
        except Exception as exc:
            raise StorageException(message=f"Failed to upsert data into {table_name}: {exc}") from exc

    def read_data(
        self,
        *,
        table_name: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> pa.Table:
        self._validate_identifier(identifier=table_name, kind="table name")

        if not self.table_exists(table_name=table_name):
            raise StorageException(message=f"Table {table_name} does not exist")

        try:
            quoted_table = self._quote_identifier(identifier=table_name)
            query = f"SELECT * FROM {quoted_table}"  # nosec B608 — identifier is validated.

            if limit is not None:
                query += " LIMIT :limit"

            if offset is not None:
                query += " OFFSET :offset"

            params: dict[str, Any] = {}

            if limit is not None:
                params["limit"] = limit

            if offset is not None:
                params["offset"] = offset

            with self.engine.connect() as connection:
                result = connection.execute(text(query), params)
                rows = result.mappings().all()
                columns = list(result.keys())

            if not rows:
                return pa.table({column: [] for column in columns})

            return pa.Table.from_pylist([dict(row) for row in rows])

        except StorageException:
            raise
        except Exception as exc:
            raise StorageException(message=f"Failed to read data from {table_name}: {exc}") from exc

    def delete_table(self, *, table_name: str) -> bool:
        self._validate_identifier(identifier=table_name, kind="table name")

        if not self.table_exists(table_name=table_name):
            return False

        try:
            quoted_table = self._quote_identifier(identifier=table_name)
            query = f"DROP TABLE IF EXISTS {quoted_table}"  # nosec B608 — identifier is validated.

            with self.engine.begin() as connection:
                connection.execute(text(query))

            logger.info("Deleted PostgreSQL table: %s", table_name)
            return True

        except Exception as exc:
            raise StorageException(message=f"Failed to delete table {table_name}: {exc}") from exc

    def table_exists(self, *, table_name: str) -> bool:
        self._validate_identifier(identifier=table_name, kind="table name")

        try:
            query = text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                )
                """
            )

            with self.engine.connect() as connection:
                return bool(connection.execute(query, {"table_name": table_name}).scalar())

        except Exception as exc:
            logger.error("Failed to check if table %s exists: %s", table_name, exc)
            return False

    def get_row_count(self, *, table_name: str) -> int:
        self._validate_identifier(identifier=table_name, kind="table name")

        if not self.table_exists(table_name=table_name):
            raise StorageException(message=f"Table {table_name} does not exist")

        try:
            quoted_table = self._quote_identifier(identifier=table_name)
            query = text(f"SELECT COUNT(*) FROM {quoted_table}")  # nosec B608 — identifier is validated.

            with self.engine.connect() as connection:
                result = connection.execute(query).scalar()

            return int(result or 0)

        except StorageException:
            raise
        except Exception as exc:
            raise StorageException(message=f"Failed to get row count for {table_name}: {exc}") from exc

    def execute_query(self, *, query: str, params: Mapping[str, Any] | None = None) -> pa.Table:
        try:
            with self.engine.connect() as connection:
                result = connection.execute(
                    text(query),
                    params or {},
                )

                rows = result.mappings().all()
                columns = list(result.keys())

            if not rows:
                return pa.table({column: [] for column in columns})

            return pa.Table.from_pylist([dict(row) for row in rows])

        except Exception as exc:
            raise StorageException(message=f"Failed to execute query: {exc}") from exc
