"""Real PostgreSQL admissions, including independent worker processes.

Set DOCPIPE_TEST_POSTGRES_DSN to an expendable PostgreSQL database URL.
Tests create a unique schema and remove only that schema during teardown.
"""

import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, inspect, select, text

from docpipe.core.incremental_metadata.adapters.stores.postgres.postgres_incremental_store import (
    PostgresIncrementalMetadataStore,
)
from docpipe.core.operators.quality.ededup_storage.adapters.postgres_store import PostgresDedupStore
from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException

_MODULE = "docpipe.core.operators.quality.ededup_storage.adapters.postgres_store"
_INCREMENTAL_MODULE = "docpipe.core.incremental_metadata.adapters.stores.postgres.postgres_incremental_store"
pytestmark = pytest.mark.integration


def _store(*, url, schema):
    with patch(f"{_MODULE}.get_postgres_connection_string", return_value=url):
        return PostgresDedupStore(config={"schema": schema})


def _incremental_store(*, url, schema):
    with patch(f"{_INCREMENTAL_MODULE}.get_postgres_connection_string", return_value=url):
        return PostgresIncrementalMetadataStore(config={"schema": schema})


def _claim_in_process(args):
    url, schema, reverse, barrier, node, run = args
    barrier.wait(timeout=30)
    store = _store(url=url, schema=schema)
    hashes = ["shared-a", "shared-b"]
    if reverse:
        hashes.reverse()
    try:
        return store.check_and_register_hashes(
            job_id="job", node_id=node, job_run_id=run, records={h: str(reverse) for h in hashes}
        )
    finally:
        store._engine.dispose()


@pytest.fixture
def database():
    url = os.getenv("DOCPIPE_TEST_POSTGRES_DSN")
    if not url:
        pytest.skip("Set DOCPIPE_TEST_POSTGRES_DSN to run PostgreSQL integration tests")
    schema = "test_ededup_" + uuid4().hex
    yield url, schema
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        engine.dispose()


def test_concurrent_processes_and_run_node_isolation(database):
    url, schema = database
    context = multiprocessing.get_context("spawn")
    with context.Manager() as manager:
        barrier = manager.Barrier(2)
        with ProcessPoolExecutor(max_workers=2, mp_context=context) as pool:
            results = list(
                pool.map(
                    _claim_in_process,
                    [(url, schema, False, barrier, "dedup", "run-a"), (url, schema, True, barrier, "dedup", "run-a")],
                )
            )
    assert results[0].isdisjoint(results[1])
    assert results[0] | results[1] == {"shared-a", "shared-b"}

    store = _store(url=url, schema=schema)
    try:

        def claim(*, run="run-a", node="dedup", job="job", doc="renamed.txt"):
            return store.check_and_register_hashes(job_id=job, node_id=node, job_run_id=run, records={"shared-a": doc})

        assert claim() == set()
        assert claim(run="run-b") == {"shared-a"}
        assert claim() == set()  # B must not overwrite A's membership.
        assert claim(node="other-branch") == {"shared-a"}
        assert claim(job="other-job") == {"shared-a"}
        with store._engine.connect() as connection:
            row = connection.execute(
                select(store._ededup_table.c.doc_id).where(store._ededup_table.c.job_run_id == "run-b")
            ).scalar_one()
        assert row == "renamed.txt"
    finally:
        store._engine.dispose()


def test_bulk_failure_rolls_back_all_chunks(database):
    url, schema = database
    store = _store(url=url, schema=schema)
    count = 0

    def fail_second_insert(*args):
        nonlocal count
        if args[2].startswith("INSERT"):
            count += 1
            if count == 2:
                raise RuntimeError("injected second chunk failure")

    event.listen(store._engine, "before_cursor_execute", fail_second_insert)
    records = {f"hash-{index:04}": str(index) for index in range(1001)}
    try:
        with pytest.raises(FlowExecutionFailedException, match="register deduplication"):
            store.check_and_register_hashes(job_id="job", node_id="node", job_run_id="run", records=records)
        event.remove(store._engine, "before_cursor_execute", fail_second_insert)
        assert store.check_and_register_hashes(job_id="job", node_id="node", job_run_id="run", records=records) == set(
            records
        )
    finally:
        store._engine.dispose()


def test_source_deletion_does_not_delete_admissions(database):
    from docpipe.core.incremental_metadata.domain.models import IncrementalMetadataRecord

    url, schema = database
    store = _store(url=url, schema=schema)
    incremental = _incremental_store(url=url, schema=schema)
    scope = {"job_id": "job", "node_id": "node", "job_run_id": "run", "records": {"hash": "old.txt"}}
    try:
        incremental.upsert_records(
            job_id="job",
            job_run_id="run",
            records=[IncrementalMetadataRecord(job_id="job", doc_id="old.txt", modified_time=1)],
        )
        assert incremental.get_processed_docs(job_id="job")["old.txt"]["job_run_id"] == "run"
        assert store.check_and_register_hashes(**scope) == {"hash"}
        incremental.delete_docs(job_id="job", doc_ids=["old.txt"])
        assert incremental.get_processed_docs(job_id="job") == {}
        assert store.check_and_register_hashes(**scope) == set()
    finally:
        store._engine.dispose()
    incremental._engine.dispose()


def test_bulk_renames_and_reopening_preserve_all_scopes(database):
    from docpipe.core.incremental_metadata.domain.models import IncrementalMetadataRecord

    url, schema = database
    store = _store(url=url, schema=schema)
    incremental = _incremental_store(url=url, schema=schema)
    scopes = [
        {"job_id": "job", "node_id": "branch-a", "job_run_id": "run-a"},
        {"job_id": "job", "node_id": "branch-b", "job_run_id": "run-a"},
        {"job_id": "job", "node_id": "branch-a", "job_run_id": "run-b"},
        {"job_id": "job", "node_id": "branch-b", "job_run_id": "run-b"},
        {"job_id": "other", "node_id": "branch-a", "job_run_id": "run-a"},
    ]
    try:
        assert set(store._ededup_table.columns.keys()) == {"job_id", "node_id", "job_run_id", "hash_value", "doc_id"}
        incremental.upsert_records(
            job_id="unrelated",
            job_run_id="run",
            records=[IncrementalMetadataRecord(job_id="unrelated", doc_id="keep", modified_time=7)],
        )
        for index, scope in enumerate(scopes):
            doc = "renamed.txt" if scope["job_run_id"] == "run-b" else f"original-{index}.txt"
            assert store.check_and_register_hashes(**scope, records={"h": doc}) == {"h"}
            assert store.check_and_register_hashes(**scope, records={"h": "same-run-rename", "new": "new.txt"}) == {
                "new"
            }
        with store._engine.connect() as connection:
            before = connection.execute(select(store._ededup_table)).mappings().all()
        assert len(before) == 10
        assert all(row["doc_id"] != "same-run-rename" for row in before)
        assert {row["doc_id"] for row in before if row["hash_value"] == "h" and row["job_run_id"] == "run-b"} == {
            "renamed.txt"
        }
        incremental_before = incremental.get_processed_docs(job_id="unrelated")
    finally:
        store._engine.dispose()

    for _ in range(2):
        reopened = _store(url=url, schema=schema)
        try:
            for scope in scopes:
                assert reopened.check_and_register_hashes(**scope, records={"h": "overwrite"}) == set()
            with reopened._engine.connect() as connection:
                after = connection.execute(select(reopened._ededup_table)).mappings().all()
            assert {tuple(sorted(row.items())) for row in after} == {tuple(sorted(row.items())) for row in before}
            assert incremental.get_processed_docs(job_id="unrelated") == incremental_before
        finally:
            reopened._engine.dispose()
    incremental._engine.dispose()


@pytest.mark.parametrize("second_scope", [("branch-b", "run-a"), ("branch-a", "run-b")])
def test_concurrent_processes_have_independent_branch_and_run_membership(database, second_scope):
    url, schema = database
    context = multiprocessing.get_context("spawn")
    with context.Manager() as manager:
        barrier = manager.Barrier(2)
        inputs = [
            (url, schema, False, barrier, "branch-a", "run-a"),
            (url, schema, True, barrier, *second_scope),
        ]
        with ProcessPoolExecutor(max_workers=2, mp_context=context) as pool:
            results = list(pool.map(_claim_in_process, inputs))
    assert results == [{"shared-a", "shared-b"}, {"shared-a", "shared-b"}]
    store = _store(url=url, schema=schema)
    try:
        assert (
            store.check_and_register_hashes(
                job_id="job", node_id="branch-a", job_run_id="run-a", records={"shared-a": "later"}
            )
            == set()
        )
    finally:
        store._engine.dispose()


def test_storage_initialization_is_independent(database):
    url, schema = database
    store = _store(url=url, schema=schema)
    try:
        assert inspect(store._engine).get_table_names(schema=schema) == ["ededup_hashes"]
        assert set(inspect(store._engine).get_pk_constraint("ededup_hashes", schema=schema)["constrained_columns"]) == {
            "job_id",
            "node_id",
            "job_run_id",
            "hash_value",
        }
    finally:
        store.close()
    incremental_schema = schema + "_incremental"
    incremental = _incremental_store(url=url, schema=incremental_schema)
    try:
        assert inspect(incremental._engine).get_table_names(schema=incremental_schema) == ["inc_update_metadata"]
    finally:
        with incremental._engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{incremental_schema}" CASCADE'))
        incremental._engine.dispose()
