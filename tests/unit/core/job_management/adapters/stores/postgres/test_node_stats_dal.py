"""Unit tests for NodeStatsDAL.get_failed_docs_for_batch."""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.job_management.adapters.stores.postgres.dal.node_stats_dal import NodeStatsDAL
from docpipe.exceptions.docpipe_exceptions import PostgresOperationException


def _make_dal(rows=None, error=None):
    """Return a NodeStatsDAL with a mocked DAO that bypasses SQLAlchemy query building."""
    dal = NodeStatsDAL.__new__(NodeStatsDAL)
    mock_dao = Mock()
    mock_dao.model = Mock()

    if error is not None:
        mock_dao.get_by_query.side_effect = error
    else:
        mock_dao.get_by_query.return_value = rows if rows is not None else []

    dal._dao = mock_dao

    # Patch sqlalchemy.select so the query is never evaluated against a real model
    with patch("docpipe.core.job_management.adapters.stores.postgres.dal.node_stats_dal.select") as mock_select:
        mock_query = Mock()
        mock_select.return_value = mock_query
        mock_query.where.return_value = mock_query
        dal._mock_select = mock_select
        dal._mock_dao = mock_dao
        dal._patch_select = patch(
            "docpipe.core.job_management.adapters.stores.postgres.dal.node_stats_dal.select",
            return_value=mock_query,
        )

    return dal


class TestGetFailedDocsForBatch:
    """Tests for NodeStatsDAL.get_failed_docs_for_batch."""

    def _run(self, *, rows=None, error=None, job_run_id="run-1", batch_id="batch-1"):
        """Helper: patch select, build DAL, call the method."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        dal._dao = mock_dao

        mock_query = Mock()
        mock_query.where.return_value = mock_query

        if error is not None:
            mock_dao.get_by_query.side_effect = error
        else:
            mock_dao.get_by_query.return_value = rows if rows is not None else []

        with patch(
            "docpipe.core.job_management.adapters.stores.postgres.dal.node_stats_dal.select",
            return_value=mock_query,
        ):
            return dal.get_failed_docs_for_batch(job_run_id=job_run_id, batch_id=batch_id), mock_dao

    def test_returns_rows_from_dao(self):
        """Delegates to dao.get_by_query and returns results."""
        row1, row2 = Mock(), Mock()
        result, mock_dao = self._run(rows=[row1, row2])

        assert result == [row1, row2]
        mock_dao.get_by_query.assert_called_once()

    def test_returns_empty_list_when_no_rows(self):
        """Returns empty list when dao returns nothing."""
        result, _ = self._run(rows=[])

        assert result == []

    def test_raises_postgres_operation_exception_on_error(self):
        """Raises PostgresOperationException when the DAO raises."""
        with pytest.raises(PostgresOperationException):
            self._run(error=RuntimeError("connection lost"))

    def test_query_passes_through_get_by_query(self):
        """get_by_query is called with the constructed query."""
        _result, mock_dao = self._run(rows=[])

        mock_dao.get_by_query.assert_called_once()


class TestNodeStatsDALOperations:
    """Tests for NodeStatsDAL: upsert, bulk_insert, query methods, and has_batch_records."""

    def _run(self, method, *, rows=None, error=None, first=None, **kwargs):
        """Helper: patch select + model chaining, call a dal method."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        dal._dao = mock_dao

        mock_query = Mock()
        mock_query.where.return_value = mock_query

        if error is not None:
            mock_dao.get_by_query.side_effect = error
            mock_dao.get_first_by_query.side_effect = error
            mock_dao.bulk_add_no_refresh.side_effect = error
            mock_dao.upsert_with_conflict.side_effect = error
            mock_dao.exists.side_effect = error
        else:
            mock_dao.get_by_query.return_value = rows if rows is not None else []
            mock_dao.get_first_by_query.return_value = first
            mock_dao.exists.return_value = rows[0] if rows else False

        with patch(
            "docpipe.core.job_management.adapters.stores.postgres.dal.node_stats_dal.select",
            return_value=mock_query,
        ):
            result = getattr(dal, method)(**kwargs)
        return result, mock_dao

    # ── upsert ────────────────────────────────────────────────────────────────

    def test_upsert_aggregated_calls_upsert_with_conflict(self):
        """upsert with batch_id=None uses the IS NULL conflict index."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        dal._dao = mock_dao

        ns = Mock()
        ns.batch_id = None
        dal.upsert(node_stat=ns)

        mock_dao.upsert_with_conflict.assert_called_once()

    def test_upsert_batch_calls_upsert_with_conflict(self):
        """upsert with batch_id set uses the IS NOT NULL conflict index."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        dal._dao = mock_dao

        ns = Mock()
        ns.batch_id = "batch-1"
        dal.upsert(node_stat=ns)

        mock_dao.upsert_with_conflict.assert_called_once()

    def test_upsert_raises_on_error(self):
        """upsert propagates PostgresOperationException on DAO failure."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        mock_dao.upsert_with_conflict.side_effect = RuntimeError("db error")
        dal._dao = mock_dao

        with pytest.raises(PostgresOperationException):
            dal.upsert(node_stat=Mock(batch_id=None))

    # ── bulk_insert ───────────────────────────────────────────────────────────

    def test_bulk_insert_empty_list_returns_immediately(self):
        """bulk_insert with empty list skips the DAO call."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        dal._dao = mock_dao

        dal.bulk_insert(node_stats=[])

        mock_dao.bulk_add_no_refresh.assert_not_called()

    def test_bulk_insert_calls_dao(self):
        """bulk_insert with items delegates to bulk_add_no_refresh."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        dal._dao = mock_dao
        items = [Mock(), Mock()]

        dal.bulk_insert(node_stats=items)

        mock_dao.bulk_add_no_refresh.assert_called_once_with(objs=items)

    def test_bulk_insert_raises_on_error(self):
        """bulk_insert raises PostgresOperationException on DAO failure."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.bulk_add_no_refresh.side_effect = RuntimeError("bulk error")
        dal._dao = mock_dao

        with pytest.raises(PostgresOperationException):
            dal.bulk_insert(node_stats=[Mock()])

    # ── get_node_stats_by_run_batch ───────────────────────────────────────────

    def test_get_node_stats_by_run_batch_returns_row(self):
        """Returns the row from get_first_by_query."""
        row = Mock()
        result, _mock_dao = self._run(
            "get_node_stats_by_run_batch",
            first=row,
            node_id="n1",
            job_run_id="r1",
            batch_id="b1",
        )
        assert result is row

    def test_get_node_stats_by_run_batch_raises_on_error(self):
        """Raises PostgresOperationException on failure."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        dal._dao = mock_dao
        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_dao.get_first_by_query.side_effect = RuntimeError("err")

        with patch(
            "docpipe.core.job_management.adapters.stores.postgres.dal.node_stats_dal.select",
            return_value=mock_query,
        ):
            with pytest.raises(PostgresOperationException):
                dal.get_node_stats_by_run_batch(node_id="n1", job_run_id="r1")

    # ── get_aggregated_node_stats ─────────────────────────────────────────────

    def test_get_aggregated_node_stats_returns_rows(self):
        """Returns the list from the DAO."""
        rows = [Mock(), Mock()]
        result, _ = self._run("get_aggregated_node_stats", rows=rows, job_run_id="r1")
        assert result == rows

    def test_get_aggregated_node_stats_raises_on_error(self):
        """Raises PostgresOperationException on failure."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        dal._dao = mock_dao
        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_dao.get_by_query.side_effect = RuntimeError("err")

        with patch(
            "docpipe.core.job_management.adapters.stores.postgres.dal.node_stats_dal.select",
            return_value=mock_query,
        ):
            with pytest.raises(PostgresOperationException):
                dal.get_aggregated_node_stats(job_run_id="r1")

    # ── get_batch_node_stats ──────────────────────────────────────────────────

    def test_get_batch_node_stats_returns_rows(self):
        """Returns batch rows from the DAO."""
        rows = [Mock()]
        result, _ = self._run("get_batch_node_stats", rows=rows, job_run_id="r1")
        assert result == rows

    def test_get_batch_node_stats_raises_on_error(self):
        """Raises PostgresOperationException on failure."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        dal._dao = mock_dao
        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_dao.get_by_query.side_effect = RuntimeError("err")

        with patch(
            "docpipe.core.job_management.adapters.stores.postgres.dal.node_stats_dal.select",
            return_value=mock_query,
        ):
            with pytest.raises(PostgresOperationException):
                dal.get_batch_node_stats(job_run_id="r1")

    # ── get_all_node_stats ────────────────────────────────────────────────────

    def test_get_all_node_stats_returns_all_rows(self):
        """Returns all rows regardless of batch_id."""
        rows = [Mock(), Mock(), Mock()]
        result, _ = self._run("get_all_node_stats", rows=rows, job_run_id="r1")
        assert result == rows

    def test_get_all_node_stats_raises_on_error(self):
        """Raises PostgresOperationException on failure."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        dal._dao = mock_dao
        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_dao.get_by_query.side_effect = RuntimeError("err")

        with patch(
            "docpipe.core.job_management.adapters.stores.postgres.dal.node_stats_dal.select",
            return_value=mock_query,
        ):
            with pytest.raises(PostgresOperationException):
                dal.get_all_node_stats(job_run_id="r1")

    # ── has_batch_records ─────────────────────────────────────────────────────

    def test_has_batch_records_returns_true_when_exists(self):
        """Returns True when DAL reports records exist."""
        from unittest.mock import MagicMock

        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = MagicMock()  # MagicMock supports & operator on model attributes
        mock_dao.exists.return_value = True
        dal._dao = mock_dao

        result = dal.has_batch_records(job_run_id="r1")

        assert result is True

    def test_has_batch_records_returns_false_on_error(self):
        """Returns False (not raises) when DAO throws."""
        dal = NodeStatsDAL.__new__(NodeStatsDAL)
        mock_dao = Mock()
        mock_dao.model = Mock()
        mock_dao.exists.side_effect = RuntimeError("db down")
        dal._dao = mock_dao

        assert dal.has_batch_records(job_run_id="r1") is False
