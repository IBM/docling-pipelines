"""
BaseDAO: A generic synchronous Data Access Object for SQLModel models.
"""

from typing import Any, Callable, TypeVar

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.expression import func
from sqlmodel import SQLModel, delete, select, update

from docpipe.exceptions.docpipe_exceptions import (
    PostgresTransactionException,
)

T = TypeVar("T", bound=SQLModel)

# Postgres refuses a statement carrying more than 65535 bind parameters.
PG_MAX_BIND_PARAMS = 65535
# Matches SQLAlchemy's insertmanyvalues page size, so chunked upserts issue the
# same number of round trips the ORM would.
MAX_UPSERT_ROWS_PER_STATEMENT = 1000


class BaseDAO[T: SQLModel]:
    """
    Generic synchronous DAO for SQLModel models.

    Provides common database operations with transaction management.
    """

    def __init__(self, *, model: type[T], session_factory: Callable[[], Session]):
        """
        Initialize the DAO.

        Args:
            model: SQLModel subclass
            session_factory: Function returning a new Session
        """
        self.model = model
        self.session_factory = session_factory

    def execute_with_session(self, *, fn: Callable[[Session], Any]) -> Any:
        """
        Run function with a fresh Session.

        Args:
            fn: Function accepting a Session

        Returns:
            Result from function

        Raises:
            PostgresTransactionException: If transaction fails
        """
        session = self.session_factory()
        try:
            result = fn(session)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            raise PostgresTransactionException(
                message=f"Transaction failed: {e}", operation="execute_with_session"
            ) from e
        finally:
            session.close()

    def get_by_id(self, *, id: Any) -> T | None:
        """Get record by primary key."""

        def op(session: Session):
            """Op."""
            return session.get(self.model, id)

        return self.execute_with_session(fn=op)

    def get_all(self) -> list[T]:
        """Get all records."""

        def op(session: Session):
            """Op."""
            statement = select(self.model)
            results = session.execute(statement)
            return list(results.scalars().all())

        return self.execute_with_session(fn=op)

    def add(self, *, obj: T) -> T:
        """Add single record with refresh."""

        def op(session: Session):
            """Op."""
            session.add(obj)
            session.flush()
            session.refresh(obj)
            return obj

        return self.execute_with_session(fn=op)

    def bulk_add_no_refresh(self, *, objs: list[T]) -> None:
        """
        Bulk add without refreshing objects - optimized for write-only operations.

        Args:
            objs: List of objects to add
        """
        if not objs:
            return

        def op(session: Session):
            """Op."""
            session.add_all(objs)
            session.flush()

        self.execute_with_session(fn=op)

    def upsert_no_refresh(self, *, obj: T) -> None:
        """
        Upsert without refreshing the object - optimized for write-only operations.
        """

        def op(session: Session):
            """Op."""
            session.merge(obj)
            session.flush()

        self.execute_with_session(fn=op)

    def upsert_with_conflict(
        self, *, obj: T, index_elements: list[str], update_fields: list[str], where_clause=None
    ) -> None:
        """
        Upsert using PostgreSQL's native INSERT ... ON CONFLICT DO UPDATE.

        Args:
            obj: The object to upsert
            index_elements: List of column names that form the unique index
            update_fields: List of field names to update on conflict
            where_clause: Optional WHERE clause for partial unique index
        """

        def op(session: Session):
            """Op."""
            values = {}
            # SQLModel instances have __table__ at runtime via SQLAlchemy
            for c in obj.__table__.columns:  # type: ignore[attr-defined]
                value = getattr(obj, c.name)
                if c.name == "id" and value is None:
                    continue
                values[c.name] = value

            stmt = pg_insert(self.model).values(**values)
            update_dict = {field: getattr(stmt.excluded, field) for field in update_fields}

            stmt = stmt.on_conflict_do_update(index_elements=index_elements, index_where=where_clause, set_=update_dict)

            session.execute(stmt)

        self.execute_with_session(fn=op)

    def _build_upsert_values(self, *, objs: list[T], index_elements: list[str]) -> list[dict[str, Any]]:
        """
        Turn model instances into row dicts for a multi-row INSERT.

        Every dict must carry the same keys: a multi-row VALUES clause renders one
        column list for the whole statement, so a row that omits a column another
        row sets fails to compile.

        Rows sharing a conflict key are collapsed, last one wins. Postgres rejects
        ON CONFLICT DO UPDATE when the same key appears twice in one statement
        ("cannot affect row a second time").

        Args:
            objs: List of model instances to upsert
            index_elements: Column names forming the conflict key

        Returns:
            Row dicts, deduplicated by conflict key, all with identical keys

        Raises:
            ValueError: If the objects do not all set the same columns
        """
        columns = [c.name for c in objs[0].__table__.columns]  # type: ignore[attr-defined]
        # An unset autoincrement id must be left out so the sequence supplies it.
        skip_id = any(getattr(obj, "id", None) is None for obj in objs)
        if skip_id and any(getattr(obj, "id", None) is not None for obj in objs):
            msg = "bulk_upsert_with_conflict requires all objects to either set id or leave it unset"
            raise ValueError(msg)
        if skip_id:
            columns = [name for name in columns if name != "id"]

        deduped: dict[tuple, dict[str, Any]] = {}
        for obj in objs:
            values = {name: getattr(obj, name) for name in columns}
            deduped[tuple(values.get(col) for col in index_elements)] = values
        return list(deduped.values())

    def bulk_upsert_with_conflict(
        self,
        *,
        objs: list[T],
        index_elements: list[str],
        update_fields: list[str],
        where_clause=None,
        session: Session | None = None,
    ) -> None:
        """
        Bulk upsert using INSERT ... ON CONFLICT DO UPDATE.

        Rows that do not exist are inserted; rows that already exist have their
        update_fields overwritten. Safe to call when rows may or may not exist.

        Rows are sent in chunks. Postgres caps a statement at 65535 bind parameters,
        so one INSERT holding every row breaks on large jobs. SQLAlchemy pages its own
        bulk inserts at 1000 rows, which is why session.add_all never hit this.

        Pass an open ``session`` to run inside an existing transaction (the caller
        owns commit/rollback). Omit it to open a fresh session that commits on success.

        Args:
            objs: List of model instances to upsert
            index_elements: Column names forming the target partial unique index
            update_fields: Field names to overwrite on conflict
            where_clause: Optional WHERE clause matching the partial unique index
            session: Optional existing session to reuse

        Raises:
            ValueError: If the objects do not all set the same columns
        """
        if not objs:
            return

        # Built outside the session so a malformed batch fails before a transaction opens.
        values_list = self._build_upsert_values(objs=objs, index_elements=index_elements)
        chunk_size = min(MAX_UPSERT_ROWS_PER_STATEMENT, max(1, PG_MAX_BIND_PARAMS // len(values_list[0])))

        def op(s: Session) -> None:
            """Op."""
            for start in range(0, len(values_list), chunk_size):
                stmt = pg_insert(self.model).values(values_list[start : start + chunk_size])
                update_dict = {field: getattr(stmt.excluded, field) for field in update_fields}
                stmt = stmt.on_conflict_do_update(
                    index_elements=index_elements, index_where=where_clause, set_=update_dict
                )
                s.execute(stmt)

        if session is not None:
            op(session)
        else:
            self.execute_with_session(fn=op)

    def delete_by_query(self, *, condition) -> int:
        """Delete records matching condition."""

        def op(session: Session):
            """Op."""
            stmt = delete(self.model).where(condition)
            result = session.execute(stmt)
            # CursorResult has rowcount at runtime
            return result.rowcount  # type: ignore[attr-defined]

        return self.execute_with_session(fn=op)

    def get_by_query(self, *, query: Select) -> list[T]:
        """Get records matching query."""

        def op(session: Session):
            """Op."""
            results = session.execute(query)
            return list(results.scalars().all())

        return self.execute_with_session(fn=op)

    def get_first_by_query(self, *, query: Select) -> T | None:
        """Get first record matching query."""

        def op(session: Session):
            """Op."""
            result = session.execute(query.limit(1))
            return result.scalar_one_or_none()

        return self.execute_with_session(fn=op)

    def exists(self, *, condition) -> bool:
        """Check if record exists matching condition."""

        def op(session: Session):
            """Op."""
            stmt = select(self.model).where(condition).limit(1)
            result = session.execute(stmt)
            return result.scalar_one_or_none() is not None

        return self.execute_with_session(fn=op)

    def run_in_transaction(self, *, fn: Callable[[Session], Any]) -> Any:
        """
        Run function in transaction with session.

        Raises:
            PostgresTransactionException: If transaction fails
        """
        session = self.session_factory()
        try:
            result = fn(session)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            raise PostgresTransactionException(
                message=f"Transaction failed: {e}", operation="run_in_transaction"
            ) from e
        finally:
            session.close()

    def atomic_increment_fields(
        self,
        *,
        condition,
        increments: dict | None = None,
        updates: dict | None = None,
        jsonb_merges: dict | None = None,
    ):
        """
        Atomically update fields with increments, direct updates, and JSONB merges.

        Args:
            condition: WHERE condition for update
            increments: Fields to increment {field_name: increment_value}
            updates: Fields to update {field_name: new_value}
            jsonb_merges: JSONB fields to merge {field_name: merge_dict}
        """

        def op(session: Session):
            """Op."""
            values = {}

            if increments:
                for column_name, increment_value in increments.items():
                    column = getattr(self.model, column_name)
                    values[column_name] = func.coalesce(column, 0) + increment_value

            if jsonb_merges:
                merged_values = self._merge_jsonb_fields(
                    session=session, condition=condition, jsonb_merges=jsonb_merges
                )
                values.update(merged_values)

            if updates:
                values.update(updates)

            if values:
                stmt = update(self.model).where(condition)
                for key, value in values.items():
                    stmt = stmt.values({key: value})
                session.execute(stmt)
                session.flush()

        self.execute_with_session(fn=op)

    def _merge_jsonb_fields(self, *, session: Session, condition, jsonb_merges: dict) -> dict:
        """Helper method to merge JSONB fields with row locking."""
        merged_values = {}
        stmt_select = select(self.model).where(condition).with_for_update()
        result = session.execute(stmt_select)
        current_row = result.scalar_one_or_none()
        if current_row:
            for column_name, new_data in jsonb_merges.items():
                existing_data = getattr(current_row, column_name, None) or {}
                merged_data = dict(existing_data)
                for key, value in new_data.items():
                    merged_data[key] = merged_data.get(key, 0) + value
                merged_values[column_name] = merged_data
        return merged_values
