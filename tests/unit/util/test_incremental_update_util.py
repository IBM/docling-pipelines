import pyarrow as pa
import pytest

from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.ingest.ingest_utils import is_doc_previously_processed
from datasift.exceptions.datasift_exceptions import FlowExecutionFailedException
from datasift.utils.data.incremental_metadata_store import (
    InMemoryIncrementalMetadataStore,
)
from datasift.utils.data.incremental_update import IncrementalUpdateUtil


@pytest.fixture
def store():
    return InMemoryIncrementalMetadataStore()


@pytest.fixture
def util(*, store):
    return IncrementalUpdateUtil(store=store)


def _build_table(*, ids: list[str], names: list[str], modified_times: list[int]) -> pa.Table:
    return pa.Table.from_pydict(
        {
            OperatorConstants.Misc.ID: ids,
            OperatorConstants.Misc.NAME: names,
            OperatorConstants.Metadata.MODIFIED_TIME: modified_times,
        }
    )


def test_incremental_update(*, util):
    job_id = "job-1"
    job_run_id = "run-1"
    time1 = 1000
    time2 = 2000

    input_table = _build_table(
        ids=["id1", "id2", "id3"],
        names=["aaa", "bbb", "ccc"],
        modified_times=[time1, time1, time1],
    )

    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[input_table])

    previously_processed_docs_dict = util.get_all_processed_docs(job_id=job_id)
    assert previously_processed_docs_dict == {"id1": time1, "id2": time1, "id3": time1}
    assert not is_doc_previously_processed(
        previously_processed_docs_dict=previously_processed_docs_dict,
        doc_id="id1",
        modified_time=time2,
    )
    assert is_doc_previously_processed(
        previously_processed_docs_dict=previously_processed_docs_dict,
        doc_id="id2",
        modified_time=time1,
    )

    updated_table = _build_table(
        ids=["id1", "id5", "id6"],
        names=["ddd", "eee", "fff"],
        modified_times=[time2, time1, time1],
    )

    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[updated_table])

    previously_processed_docs_dict = util.get_all_processed_docs(job_id=job_id)
    assert previously_processed_docs_dict == {
        "id1": time2,
        "id2": time1,
        "id3": time1,
        "id5": time1,
        "id6": time1,
    }


def test_get_deleted_docs(*, util, store):
    job_id = "job-1"
    job_run_id = "run-1"

    input_table = _build_table(
        ids=["id1", "id2", "id3", "id4"],
        names=["aaa", "bbb", "ccc", "zzz"],
        modified_times=[1000, 1000, 1000, 1000],
    )
    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[input_table])

    store.mark_missing_docs_as_deleted(job_id=job_id, doc_ids=["id1", "id2", "id4"])
    soft_deleted_ids = util.get_soft_deleted_doc_ids(job_id=job_id)
    assert soft_deleted_ids == {"id3"}

    deleted_doc_ids = util.mark_soft_deleted_docs(job_id=job_id, doc_ids=["id4", "id2"])
    assert deleted_doc_ids == {"id1"}
    assert util.get_soft_deleted_doc_ids(job_id=job_id) == {"id1"}


def test_delete_failed_doc(*, util):
    job_id = "job-1"
    job_run_id = "run-1"

    input_table = _build_table(
        ids=["id1", "id2", "id3"],
        names=["doc1", "doc2", "doc3"],
        modified_times=[1000, 2000, 3000],
    )
    result_table = _build_table(
        ids=["id1", "id3"],
        names=["doc1", "doc3"],
        modified_times=[1000, 3000],
    )

    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[input_table])
    remaining_ids = util.delete_failed_doc(table=input_table, result_table=result_table, job_id=job_id)

    assert remaining_ids == {"id1", "id2", "id3"}
    assert util.get_all_processed_docs(job_id=job_id) == {"id1": 1000, "id3": 3000}


def test_delete_failed_doc_empty_tables(*, util):
    empty_table = _build_table(ids=[], names=[], modified_times=[])

    remaining_ids = util.delete_failed_doc(table=empty_table, result_table=empty_table, job_id="job-1")

    assert remaining_ids == set()


def test_delete_failed_doc_all_failed(*, util):
    job_id = "job-1"
    job_run_id = "run-1"

    input_table = _build_table(
        ids=["id1", "id2"],
        names=["doc1", "doc2"],
        modified_times=[1000, 2000],
    )
    result_table = _build_table(ids=[], names=[], modified_times=[])

    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[input_table])
    remaining_ids = util.delete_failed_doc(table=input_table, result_table=result_table, job_id=job_id)

    assert remaining_ids == {"id1", "id2"}
    assert util.get_all_processed_docs(job_id=job_id) == {}


def test_get_deleted_doc_ids_from_dict(*, util):
    previously_processed = {"id1": 1000, "id2": 2000, "id3": 3000, "id4": 4000}
    current_docs = ["id1", "id3"]

    deleted_ids = util.get_deleted_doc_ids_from_dict(
        previously_processed_docs_dict=previously_processed,
        doc_ids=current_docs,
    )

    assert set(deleted_ids) == {"id2", "id4"}


def test_get_deleted_doc_ids_from_dict_empty_previous(*, util):
    assert util.get_deleted_doc_ids_from_dict(previously_processed_docs_dict={}, doc_ids=["id1", "id2"]) == []


def test_get_deleted_doc_ids_from_dict_none_previous(*, util):
    assert util.get_deleted_doc_ids_from_dict(previously_processed_docs_dict=None, doc_ids=["id1", "id2"]) == []


def test_get_deleted_doc_ids_from_dict_no_deletions(*, util):
    previously_processed = {"id1": 1000, "id2": 2000}
    current_docs = ["id1", "id2"]

    assert (
        util.get_deleted_doc_ids_from_dict(previously_processed_docs_dict=previously_processed, doc_ids=current_docs)
        == []
    )


def test_clear_incremental_table(*, util):
    job_id = "job-1"
    job_run_id = "run-1"
    table = _build_table(ids=["id1", "id2"], names=["doc1", "doc2"], modified_times=[1000, 2000])

    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[table])
    assert util.get_all_processed_docs(job_id=job_id) == {"id1": 1000, "id2": 2000}

    util.clear_incremental_table(job_id=job_id)

    assert util.get_all_processed_docs(job_id=job_id) == {}
    assert util.get_soft_deleted_doc_ids(job_id=job_id) == set()


def test_save_metadata_exception_handling(*, util, mocker):
    table = _build_table(ids=["id1"], names=["doc1"], modified_times=[1000])
    mocker.patch.object(util.store, "upsert_records", side_effect=Exception("store failure"))

    with pytest.raises(FlowExecutionFailedException, match="store failure"):
        util.save_metadata_for_incremental_update(job_id="job-1", job_run_id="run-1", tables=[table])


def test_get_all_processed_docs_exception_handling(*, util, mocker):
    mocker.patch.object(util.store, "get_processed_docs", side_effect=Exception("read failure"))

    with pytest.raises(FlowExecutionFailedException, match="read failure"):
        util.get_all_processed_docs(job_id="job-1")


def test_mark_soft_deleted_docs_exception_handling(*, util, mocker):
    mocker.patch.object(util.store, "mark_missing_docs_as_deleted", side_effect=Exception("mark failure"))

    with pytest.raises(FlowExecutionFailedException, match="mark failure"):
        util.mark_soft_deleted_docs(job_id="job-1", doc_ids=["id1"])


def test_get_soft_deleted_doc_ids_exception_handling(*, util, mocker):
    mocker.patch.object(util.store, "get_soft_deleted_doc_ids", side_effect=Exception("deleted failure"))

    with pytest.raises(FlowExecutionFailedException, match="deleted failure"):
        util.get_soft_deleted_doc_ids(job_id="job-1")


def test_delete_docs_for_ids_exception_handling(*, util, mocker):
    mocker.patch.object(util.store, "delete_docs", side_effect=Exception("delete failure"))

    with pytest.raises(FlowExecutionFailedException, match="delete failure"):
        util.delete_docs_for_ids(doc_ids=["id1"], job_id="job-1")


def test_get_table_exception_handling(*, util):
    with pytest.raises(FlowExecutionFailedException):
        util._get_table(path="/invalid/path/table.parquet")


def test_save_metadata_with_empty_tables(*, util):
    empty_table = _build_table(ids=[], names=[], modified_times=[])

    util.save_metadata_for_incremental_update(job_id="job-1", job_run_id="run-1", tables=[empty_table])

    assert util.get_all_processed_docs(job_id="job-1") == {}


def test_save_metadata_with_multiple_empty_tables(*, util):
    empty_tables = [_build_table(ids=[], names=[], modified_times=[]) for _ in range(3)]

    util.save_metadata_for_incremental_update(job_id="job-1", job_run_id="run-1", tables=empty_tables)

    assert util.get_all_processed_docs(job_id="job-1") == {}


def test_get_all_processed_docs_empty_table(*, util):
    assert util.get_all_processed_docs(job_id="job-1") == {}


def test_mark_soft_deleted_docs_empty_table(*, util):
    result = util.mark_soft_deleted_docs(job_id="job-1", doc_ids=["id1", "id2"])
    assert result == set()


def test_mark_soft_deleted_docs_with_zero_rows(*, util):
    empty_table = _build_table(ids=[], names=[], modified_times=[])

    util.save_metadata_for_incremental_update(job_id="job-1", job_run_id="run-1", tables=[empty_table])
    result = util.mark_soft_deleted_docs(job_id="job-1", doc_ids=["id1", "id2"])

    assert result == set()


def test_filter_rows_with_none_table(*, util):
    assert util.filter_rows(table=None, ids_to_delete=["id1"]) is None


def test_filter_rows_with_none_ids(*, util):
    table = _build_table(ids=["id1", "id2"], names=["doc1", "doc2"], modified_times=[1000, 2000])
    assert util.filter_rows(table=table, ids_to_delete=None) == table


def test_filter_rows_with_empty_ids(*, util):
    table = _build_table(ids=["id1", "id2"], names=["doc1", "doc2"], modified_times=[1000, 2000])
    assert util.filter_rows(table=table, ids_to_delete=[]) == table


def test_delete_docs_for_ids_empty_list(*, util):
    util.delete_docs_for_ids(doc_ids=[], job_id="job-1")
    assert util.get_all_processed_docs(job_id="job-1") == {}


def test_save_metadata_with_failed_doc_ids(*, util):
    table = _build_table(
        ids=["id1", "id2", "id3"],
        names=["doc1", "doc2", "doc3"],
        modified_times=[1000, 2000, 3000],
    )

    util.save_metadata_for_incremental_update(
        job_id="job-1",
        job_run_id="run-1",
        tables=[table],
        failed_doc_ids=["id2"],
    )

    assert util.get_all_processed_docs(job_id="job-1") == {"id1": 1000, "id3": 3000}


def test_get_soft_deleted_ids_with_none_table(*, util):
    assert util._get_soft_deleted_ids(table=None) == set()


def test_get_soft_deleted_ids_with_empty_table(*, util):
    empty_table = pa.Table.from_pydict({OperatorConstants.Misc.ID: [], OperatorConstants.Misc.DELETED: []})
    assert util._get_soft_deleted_ids(table=empty_table) == set()


def test_get_ids_to_delete_with_empty_input(*, util):
    empty_table = pa.Table.from_pydict({OperatorConstants.Misc.ID: []})
    result_table = pa.Table.from_pydict({OperatorConstants.Misc.ID: ["id1"]})

    assert util._get_ids_to_delete(input_table=empty_table, result_table=result_table) == []


def test_get_ids_to_delete_with_empty_result(*, util):
    input_table = pa.Table.from_pydict({OperatorConstants.Misc.ID: ["id1", "id2"]})
    empty_table = pa.Table.from_pydict({OperatorConstants.Misc.ID: []})

    assert set(util._get_ids_to_delete(input_table=input_table, result_table=empty_table)) == {"id1", "id2"}


def test_mark_docs_to_delete_with_none_table(*, util):
    result_table, deleted_ids = util._mark_docs_to_delete(table=None, doc_ids={"id1", "id2"})
    assert result_table is None
    assert deleted_ids == {"id1", "id2"}


def test_mark_docs_to_delete_with_empty_table(*, util):
    empty_table = pa.Table.from_pydict({OperatorConstants.Misc.ID: [], OperatorConstants.Misc.DELETED: []})

    result_table, deleted_ids = util._mark_docs_to_delete(table=empty_table, doc_ids={"id1", "id2"})
    assert result_table is None
    assert deleted_ids == {"id1", "id2"}


def test_concatenate_tables_with_overlapping_ids(*, util):
    table1 = pa.Table.from_pydict(
        {
            OperatorConstants.Misc.ID: ["id1", "id2"],
            OperatorConstants.Misc.NAME: ["doc1_new", "doc2_new"],
        }
    )
    table2 = pa.Table.from_pydict(
        {
            OperatorConstants.Misc.ID: ["id2", "id3"],
            OperatorConstants.Misc.NAME: ["doc2_old", "doc3"],
        }
    )

    result = util.concatenate_tables(table1=table1, table2=table2)

    assert result.num_rows == 3
    result_ids = result[OperatorConstants.Misc.ID].to_pylist()
    assert "id1" in result_ids
    assert "id2" in result_ids
    assert "id3" in result_ids

    result_dict = {row[OperatorConstants.Misc.ID]: row[OperatorConstants.Misc.NAME] for row in result.to_pylist()}
    assert result_dict["id2"] == "doc2_new"

def test_incremental_update_util_with_flow_config(*, tmp_path):
    flow_config = {
        "storage_type": "file_system",
        "config": {
            "base_dir": str(tmp_path / "flow_incremental"),
            "lock_timeout": 5.0,
        },
    }

    util = IncrementalUpdateUtil(flow_config=flow_config)

    assert util.store is not None
    from datasift.utils.data.incremental_metadata_store import FileSystemIncrementalMetadataStore

    assert isinstance(util.store, FileSystemIncrementalMetadataStore)
    assert util.store._base_dir == tmp_path / "flow_incremental"


def test_incremental_update_util_with_inmemory_flow_config():
    flow_config = {"storage_type": "in_memory", "config": {}}

    util = IncrementalUpdateUtil(flow_config=flow_config)

    assert util.store is not None
    from datasift.utils.data.incremental_metadata_store import InMemoryIncrementalMetadataStore

    assert isinstance(util.store, InMemoryIncrementalMetadataStore)


def test_incremental_update_util_store_takes_precedence_over_flow_config(*, store):
    flow_config = {"storage_type": "file_system", "config": {"base_dir": "/some/path"}}

    util = IncrementalUpdateUtil(store=store, flow_config=flow_config)

    assert util.store is store


def test_incremental_update_util_without_config_uses_default():
    util = IncrementalUpdateUtil()

    assert util.store is not None
