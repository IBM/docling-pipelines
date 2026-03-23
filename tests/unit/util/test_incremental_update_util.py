import os
import shutil
import time
from unittest.mock import MagicMock, patch
from uuid import uuid1

import pyarrow as pa
from common.constants.operator_constants import OperatorConstants
from common.util.iceberg_util import get_warehouse_path
from common.util.incremental_update_util import IncrementalUpdateUtil
from common.util.parquet_table_handler import CpdParquetTableHandler
from core.operators.ingest.ingest_utils import is_doc_previously_processed
from ibm_botocore.exceptions import ClientError
from pyarrow import parquet as pq


def test_incremental_update():
    util = IncrementalUpdateUtil()

    full_path = os.path.join(get_warehouse_path(path=util.INCREMENTAL_PROCESSING_METADATA_PATH))
    if os.path.exists(full_path):
        shutil.rmtree(full_path)

    # Save incremental update metadata into Iceberg with overwrite = true to delete all previously created data
    job_id = str(uuid1())
    job_run_id = str(uuid1())
    id1 = str(uuid1())
    id2 = str(uuid1())
    id3 = str(uuid1())
    ids = pa.array([id1, id2, id3])
    data = pa.array([
        "Contact support team via eamil:  support@ibm.com, or the sales team sales@in.ibm.com.",
        "My personal email id is jj@acm.org",
        "No matches in this row"
    ])
    text_embeddings = [[1.5, 2.6, 3.7], [4.5, 6.9, 4.4], [1.1, 2.3, 3.2]]
    doc_names = pa.array(["aaa", "bbb", "ccc"])
    time1 = round(time.time() * 1000)
    times = pa.array([time1, time1, time1])
    input_table = pa.Table.from_arrays(
        [data, text_embeddings, ids, doc_names, times],
        names=[OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
               OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT, OperatorConstants.Columns.ID,
               OperatorConstants.Columns.NAME, OperatorConstants.Metadata.MODIFIED_TIME])

    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[input_table])

    # Validate that only required columns are saved in Iceberg
    table = util.parquet_table_handler.read_table(path=util.construct_table_path(job_id=job_id))
    assert table.num_rows == 3
    expected_column_names = ['id', 'name', 'modified_time', 'job_id', 'job_run_id','deleted']
    assert expected_column_names == table.column_names, f"Column names in the resulting table ({table.column_names}) does not match expected number ({expected_column_names})"

    time2 = round(time.time() * 1000)
    previously_processed_docs_dict = util.get_all_processed_docs(job_id=job_id)
    assert previously_processed_docs_dict is not None
    # test by passing new(time2) file_modified_time for id1 and same(time1) file_modified_time for id2
    assert not is_doc_previously_processed(previously_processed_docs_dict=previously_processed_docs_dict, doc_id=id1, modified_time=time2)
    assert is_doc_previously_processed(previously_processed_docs_dict=previously_processed_docs_dict, doc_id=id2, modified_time=time1)

    # Save incremental update metadata for another set of documents, where the first doc is updated (ID is same)
    str(uuid1())
    id5 = str(uuid1())
    id6 = str(uuid1())
    ids = pa.array([id1, id5, id6])   # Note the ID of the first doc is not changed
    data = pa.array([
        "Contact support team via eamil:  support@ibm.com, or the sales team sales@in.ibm.com.",
        "My personal email id is jj@acm.org",
        "No matches in this row"
    ])
    text_embeddings = [[1.5, 2.6, 3.7], [4.5, 6.9, 4.4], [1.1, 2.3, 3.2]]
    doc_names = pa.array(["ddd", "eee", "fff"])
    # time1 = round(time.time() * 1000)
    times = pa.array([time1, time1, time1])
    input_table = pa.Table.from_arrays(
        [data, text_embeddings, ids, doc_names, times],
        names=[OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
               OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT, OperatorConstants.Columns.ID,
               OperatorConstants.Columns.NAME, OperatorConstants.Metadata.MODIFIED_TIME])

    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[input_table])

    # Validate that only required columns are saved in Iceberg
    table = util.parquet_table_handler.read_table(path=util.construct_table_path(job_id=job_id))
    assert table.num_rows == 5

    time2 = round(time.time() * 1000)

    previously_processed_docs_dict = util.get_all_processed_docs(job_id=job_id)
    assert previously_processed_docs_dict is not None
    # test by passing new(time2) file_modified_time for id1 and same(time1) file_modified_time for id2
    assert not is_doc_previously_processed(previously_processed_docs_dict=previously_processed_docs_dict, doc_id=id1, modified_time=time2)
    assert is_doc_previously_processed(previously_processed_docs_dict=previously_processed_docs_dict, doc_id=id2, modified_time=time1)

def test_get_deleted_docs():
    util  = IncrementalUpdateUtil()

    job_id = str(uuid1())
    job_run_id = str(uuid1())
    id1 = str(uuid1())
    id2 = str(uuid1())
    id3 = str(uuid1())
    id4 = str(uuid1())
    ids = pa.array([id1, id2, id3, id4])
    data = pa.array([
        "Contact support team via eamil:  support@ibm.com, or the sales team sales@in.ibm.com.",
        "My personal email id is jj@acm.org",
        "No matches in this row",
        "deleted record additions"
    ])
    text_embeddings = [[1.5, 2.6, 3.7, 5.4], [4.5, 6.9, 4.4, 3.2], [1.1, 2.3, 3.2,6.4], [3.2, 4, 5.2 , 5.3]]
    doc_names = pa.array(["aaa", "bbb", "ccc","zzz"])
    time1 = round(time.time() * 1000)
    #id3 is the value to set true to test the function
    times = pa.array([time1, time1, time1, time1])
    input_table = pa.Table.from_arrays(
        [data, text_embeddings, ids, doc_names, times],
        names=[OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
               OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT, OperatorConstants.Columns.ID,
               OperatorConstants.Columns.NAME, OperatorConstants.Metadata.MODIFIED_TIME])
    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[input_table])
    #validate save records
    table_path = util.construct_table_path(job_id=job_id)
    table = util.parquet_table_handler.read_table(path=table_path)
    df = table.to_pandas()
    df.loc[df[OperatorConstants.Columns.ID] == id3, OperatorConstants.Misc.DELETED] = True
    updated_table = pa.Table.from_pandas(df)
    util.parquet_table_handler.save_table(path=table_path, table=updated_table)
    assert table.num_rows == 4

    soft_deleted_ids = util.get_soft_deleted_doc_ids(job_id=job_id)
    assert len(soft_deleted_ids) == 1
    assert soft_deleted_ids == {id3}

    deleted_doc_ids = util.mark_soft_deleted_docs(job_id=job_id, doc_ids=[id4,id2])
    table_updated = util.parquet_table_handler.read_table(path=table_path)
    assert table_updated.num_rows == 3
    assert deleted_doc_ids == {id1}

def test_delete_file_success_cpd():
    mock_table = pa.Table.from_pydict({"id": [1, 2, 3], "name": ["a", "b", "c"], "modified_time" : [1, 2, 3]})
    util = IncrementalUpdateUtil()
    job_id = str(uuid1())
    job_run_id = str(uuid1())
    util.save_metadata_for_incremental_update(job_id=job_id, job_run_id=job_run_id, tables=[mock_table])
    table_path = util.construct_table_path(job_id=job_id)
    util.parquet_table_handler.delete_file(path=table_path)


def test_delete_file_exception_cpd():
    with patch("common.util.parquet_table_handler.get_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        util = IncrementalUpdateUtil()
        table_path = util.construct_table_path(job_id=str(uuid1()))

        with patch("os.remove", side_effect=Exception("Mock removal error")):
            with patch("os.path.exists", return_value=True):
                with patch("common.util.parquet_table_handler._lock_path", return_value="/mock.lock"):
                    with patch("common.util.parquet_table_handler.FileLock"):
                        util.parquet_table_handler.delete_file(path=table_path)

        mock_logger.error.assert_called_once()
        args, _ = mock_logger.error.call_args
        assert "Mock removal error" in args[0]
