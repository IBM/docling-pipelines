"""Unit tests for BaseDAO using mock SQLAlchemy sessions."""

from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.job_management.adapters.stores.postgres.dal.base_dao import BaseDAO
from docpipe.exceptions.docpipe_exceptions import PostgresTransactionException


class FakeModel:
    """Minimal stand-in for a SQLModel subclass."""


def make_dao():
    mock_session = MagicMock()
    dao = BaseDAO(model=FakeModel, session_factory=lambda: mock_session)
    return dao, mock_session


def make_dao_with_session():
    """Return (dao, mock_session) where execute_with_session runs the real code."""
    mock_session = MagicMock()
    dao = BaseDAO(model=FakeModel, session_factory=lambda: mock_session)
    return dao, mock_session


class TestExecuteWithSession:
    def test_commits_and_returns_result(self):
        dao, mock_session = make_dao()
        result = dao.execute_with_session(fn=lambda s: "ok")
        assert result == "ok"
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_rolls_back_and_raises_on_exception(self):
        dao, mock_session = make_dao()
        with pytest.raises(PostgresTransactionException):
            dao.execute_with_session(fn=lambda s: (_ for _ in ()).throw(RuntimeError("db error")))
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    def test_close_called_even_after_rollback(self):
        dao, mock_session = make_dao()
        mock_session.commit.side_effect = RuntimeError("commit failed")
        with pytest.raises(PostgresTransactionException):
            dao.execute_with_session(fn=lambda s: None)
        mock_session.close.assert_called_once()


class TestGetById:
    def test_returns_object_when_found(self):
        dao, mock_session = make_dao()
        obj = FakeModel()
        mock_session.get.return_value = obj
        result = dao.get_by_id(id="id1")
        assert result is obj
        mock_session.get.assert_called_once_with(FakeModel, "id1")

    def test_returns_none_when_not_found(self):
        dao, mock_session = make_dao()
        mock_session.get.return_value = None
        assert dao.get_by_id(id="missing") is None


class TestGetAll:
    def test_returns_all_objects(self):
        dao, _ = make_dao()
        o1, o2 = FakeModel(), FakeModel()
        with patch.object(dao, "execute_with_session", return_value=[o1, o2]):
            result = dao.get_all()
        assert result == [o1, o2]

    def test_get_all_executes_select(self):
        """Covers the inner op closure in get_all (lines 78-80)."""
        dao, mock_session = make_dao_with_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [FakeModel(), FakeModel()]
        mock_session.execute.return_value.scalars.return_value = scalars_mock
        with patch("docpipe.core.job_management.adapters.stores.postgres.dal.base_dao.select"):
            result = dao.get_all()
        assert mock_session.execute.called
        assert isinstance(result, list)


class TestAdd:
    def test_adds_flushes_and_refreshes(self):
        dao, mock_session = make_dao()
        obj = FakeModel()
        result = dao.add(obj=obj)
        mock_session.add.assert_called_once_with(obj)
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(obj)
        assert result is obj


class TestBulkAddNoRefresh:
    def test_empty_list_skips_session(self):
        dao, mock_session = make_dao()
        dao.bulk_add_no_refresh(objs=[])
        mock_session.add_all.assert_not_called()

    def test_non_empty_adds_all(self):
        dao, mock_session = make_dao()
        objs = [FakeModel(), FakeModel()]
        dao.bulk_add_no_refresh(objs=objs)
        mock_session.add_all.assert_called_once_with(objs)
        mock_session.flush.assert_called_once()


class TestUpsertNoRefresh:
    def test_merges_object(self):
        dao, mock_session = make_dao()
        obj = FakeModel()
        dao.upsert_no_refresh(obj=obj)
        mock_session.merge.assert_called_once_with(obj)
        mock_session.flush.assert_called_once()


class TestDeleteByQuery:
    def test_returns_rowcount(self):
        dao, _ = make_dao()
        condition = MagicMock()
        with patch.object(dao, "execute_with_session", return_value=3):
            result = dao.delete_by_query(condition=condition)
        assert result == 3

    def test_delete_by_query_executes_delete(self):
        """Covers the inner op closure in delete_by_query (lines 162-165)."""
        dao, mock_session = make_dao_with_session()
        mock_session.execute.return_value.rowcount = 2
        condition = MagicMock()
        with patch("docpipe.core.job_management.adapters.stores.postgres.dal.base_dao.delete") as mock_delete:
            mock_delete.return_value.where.return_value = MagicMock()
            result = dao.delete_by_query(condition=condition)
        assert mock_session.execute.called
        assert result == 2


class TestGetByQuery:
    def test_returns_list_of_objects(self):
        dao, _ = make_dao()
        o1 = FakeModel()
        with patch.object(dao, "execute_with_session", return_value=[o1]):
            result = dao.get_by_query(query=MagicMock())
        assert result == [o1]

    def test_get_by_query_executes_query(self):
        """Covers the inner op closure in get_by_query (lines 174-175)."""
        dao, mock_session = make_dao_with_session()
        o1 = FakeModel()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [o1]
        mock_session.execute.return_value.scalars.return_value = scalars_mock
        query = MagicMock()
        result = dao.get_by_query(query=query)
        assert mock_session.execute.called
        assert result == [o1]


class TestGetFirstByQuery:
    def test_returns_first_object(self):
        dao, _ = make_dao()
        obj = FakeModel()
        with patch.object(dao, "execute_with_session", return_value=obj):
            result = dao.get_first_by_query(query=MagicMock())
        assert result is obj

    def test_returns_none_when_empty(self):
        dao, _ = make_dao()
        with patch.object(dao, "execute_with_session", return_value=None):
            assert dao.get_first_by_query(query=MagicMock()) is None

    def test_get_first_by_query_executes_query(self):
        """Covers the inner op closure in get_first_by_query (lines 184-185)."""
        dao, mock_session = make_dao_with_session()
        obj = FakeModel()
        query = MagicMock()
        query.limit.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = obj
        result = dao.get_first_by_query(query=query)
        assert result is obj


class TestExists:
    def test_returns_true_when_found(self):
        dao, _ = make_dao()
        with patch.object(dao, "execute_with_session", return_value=True):
            assert dao.exists(condition=MagicMock()) is True

    def test_returns_false_when_not_found(self):
        dao, _ = make_dao()
        with patch.object(dao, "execute_with_session", return_value=False):
            assert dao.exists(condition=MagicMock()) is False

    def test_exists_executes_select(self):
        """Covers the inner op closure in exists (lines 194-196)."""
        dao, mock_session = make_dao_with_session()
        obj = FakeModel()
        mock_session.execute.return_value.scalar_one_or_none.return_value = obj
        condition = MagicMock()
        with patch("docpipe.core.job_management.adapters.stores.postgres.dal.base_dao.select") as mock_select:
            mock_select.return_value.where.return_value.limit.return_value = MagicMock()
            result = dao.exists(condition=condition)
        assert result is True


class TestRunInTransaction:
    def test_commits_and_returns(self):
        dao, mock_session = make_dao()
        result = dao.run_in_transaction(fn=lambda s: "txn_result")
        assert result == "txn_result"
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_rolls_back_on_failure(self):
        dao, mock_session = make_dao()
        with pytest.raises(PostgresTransactionException):
            dao.run_in_transaction(fn=lambda s: (_ for _ in ()).throw(RuntimeError("fail")))
        mock_session.rollback.assert_called_once()


class TestAtomicIncrementFields:
    def test_no_op_when_nothing_specified(self):
        dao, mock_session = make_dao()
        dao.atomic_increment_fields(condition=MagicMock())
        mock_session.flush.assert_not_called()

    def test_updates_fields(self):
        dao, _ = make_dao()
        with patch.object(dao, "execute_with_session") as mock_exec:
            dao.atomic_increment_fields(
                condition=MagicMock(),
                updates={"status": "done"},
            )
            mock_exec.assert_called_once()

    def test_increments_fields(self):
        dao, _ = make_dao()
        # Patch execute_with_session since update() requires real SQLModel table
        with patch.object(dao, "execute_with_session") as mock_exec:
            FakeModel.count = MagicMock()  # type: ignore[attr-defined]
            dao.atomic_increment_fields(
                condition=MagicMock(),
                increments={"count": 1},
            )
            mock_exec.assert_called_once()


class TestUpsertWithConflict:
    def test_upsert_with_conflict_executes_insert(self):
        """Covers the inner op closure in upsert_with_conflict (lines 138-155)."""
        dao, mock_session = make_dao_with_session()

        class FakeCol:
            def __init__(self, name):
                self.name = name

        class FakeTable:
            columns: ClassVar[list] = [FakeCol("id"), FakeCol("name"), FakeCol("status")]

        obj = FakeModel()
        obj.__table__ = FakeTable()  # type: ignore[attr-defined]
        obj.id = None  # type: ignore[attr-defined]
        obj.name = "test"  # type: ignore[attr-defined]
        obj.status = "running"  # type: ignore[attr-defined]

        with patch("docpipe.core.job_management.adapters.stores.postgres.dal.base_dao.pg_insert") as mock_insert:
            mock_stmt = MagicMock()
            mock_stmt.on_conflict_do_update.return_value = mock_stmt
            mock_stmt.excluded = MagicMock()
            mock_insert.return_value.values.return_value = mock_stmt
            dao.upsert_with_conflict(
                obj=obj,
                index_elements=["name"],
                update_fields=["status"],
            )
        assert mock_session.execute.called


class TestAtomicIncrementFieldsClosures:
    def test_atomic_increment_with_increments_executes_update(self):
        """Covers increments branch inside atomic_increment_fields closure (lines 242-261)."""
        dao, mock_session = make_dao_with_session()
        # Give FakeModel an attribute so getattr(self.model, column_name) doesn't fail
        FakeModel.count = MagicMock()  # type: ignore[attr-defined]
        mock_session.execute.return_value = MagicMock()

        with patch("docpipe.core.job_management.adapters.stores.postgres.dal.base_dao.update") as mock_update:
            mock_stmt = MagicMock()
            mock_update.return_value.where.return_value = mock_stmt
            mock_stmt.values.return_value = mock_stmt
            with patch("docpipe.core.job_management.adapters.stores.postgres.dal.base_dao.func") as mock_func:
                mock_func.coalesce.return_value = MagicMock()
                dao.atomic_increment_fields(
                    condition=MagicMock(),
                    increments={"count": 1},
                )
        assert mock_session.execute.called

    def test_atomic_increment_with_jsonb_merge_executes_update(self):
        """Covers jsonb_merges branch inside atomic_increment_fields closure (lines 247-261)."""
        dao, mock_session = make_dao_with_session()
        mock_session.execute.return_value = MagicMock()

        with patch.object(dao, "_merge_jsonb_fields", return_value={"metadata": {"count": 1}}):
            with patch("docpipe.core.job_management.adapters.stores.postgres.dal.base_dao.update") as mock_update:
                mock_stmt = MagicMock()
                mock_update.return_value.where.return_value = mock_stmt
                mock_stmt.values.return_value = mock_stmt
                dao.atomic_increment_fields(
                    condition=MagicMock(),
                    jsonb_merges={"metadata": {"count": 1}},
                )
        assert mock_session.execute.called

    def test_merge_jsonb_fields_no_current_row(self):
        """Covers _merge_jsonb_fields when no existing row found (lines 265-278)."""
        dao, mock_session = make_dao_with_session()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch("docpipe.core.job_management.adapters.stores.postgres.dal.base_dao.select") as mock_select:
            mock_select.return_value.where.return_value.with_for_update.return_value = MagicMock()
            result = dao._merge_jsonb_fields(
                session=mock_session,
                condition=MagicMock(),
                jsonb_merges={"metadata": {"count": 1}},
            )
        assert result == {}

    def test_merge_jsonb_fields_merges_existing(self):
        """Covers _merge_jsonb_fields when row exists (lines 271-278)."""
        dao, mock_session = make_dao_with_session()
        existing_row = MagicMock()
        existing_row.metadata = {"count": 5}
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing_row

        with patch("docpipe.core.job_management.adapters.stores.postgres.dal.base_dao.select") as mock_select:
            mock_select.return_value.where.return_value.with_for_update.return_value = MagicMock()
            result = dao._merge_jsonb_fields(
                session=mock_session,
                condition=MagicMock(),
                jsonb_merges={"metadata": {"count": 3}},
            )
        assert result["metadata"]["count"] == 8
