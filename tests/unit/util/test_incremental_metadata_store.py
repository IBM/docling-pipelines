import json

import pytest

from datasift.utils.data.incremental_metadata_store import (
    FileSystemIncrementalMetadataStore,
    IncrementalMetadataRecord,
    InMemoryIncrementalMetadataStore,
)


@pytest.fixture
def sample_records():
    return [
        IncrementalMetadataRecord(
            job_id="job-1",
            doc_id="doc-1",
            name="doc1",
            modified_time=1000,
            job_run_id="run-1",
            deleted=False,
        ),
        IncrementalMetadataRecord(
            job_id="job-1",
            doc_id="doc-2",
            name="doc2",
            modified_time=2000,
            job_run_id="run-1",
            deleted=False,
        ),
    ]


class TestInMemoryIncrementalMetadataStore:
    def test_upsert_and_get_processed_docs(self, *, sample_records):
        store = InMemoryIncrementalMetadataStore()

        store.upsert_records(job_id="job-1", job_run_id="run-1", records=sample_records)

        assert store.get_processed_docs(job_id="job-1") == {
            "doc-1": 1000,
            "doc-2": 2000,
        }

    def test_upsert_overwrites_existing_doc(self, *, sample_records):
        store = InMemoryIncrementalMetadataStore()
        store.upsert_records(job_id="job-1", job_run_id="run-1", records=sample_records)

        store.upsert_records(
            job_id="job-1",
            job_run_id="run-2",
            records=[
                IncrementalMetadataRecord(
                    job_id="job-1",
                    doc_id="doc-1",
                    name="doc1-updated",
                    modified_time=3000,
                    job_run_id="run-2",
                    deleted=False,
                )
            ],
        )

        assert store.get_processed_docs(job_id="job-1") == {
            "doc-1": 3000,
            "doc-2": 2000,
        }

    def test_mark_missing_docs_as_deleted(self, *, sample_records):
        store = InMemoryIncrementalMetadataStore()
        store.upsert_records(job_id="job-1", job_run_id="run-1", records=sample_records)

        deleted_ids = store.mark_missing_docs_as_deleted(job_id="job-1", doc_ids=["doc-2"])

        assert deleted_ids == {"doc-1"}
        assert store.get_processed_docs(job_id="job-1") == {"doc-2": 2000}
        assert store.get_soft_deleted_doc_ids(job_id="job-1") == {"doc-1"}

    def test_delete_docs(self, *, sample_records):
        store = InMemoryIncrementalMetadataStore()
        store.upsert_records(job_id="job-1", job_run_id="run-1", records=sample_records)

        store.delete_docs(job_id="job-1", doc_ids=["doc-2"])

        assert store.get_processed_docs(job_id="job-1") == {"doc-1": 1000}

    def test_clear(self, *, sample_records):
        store = InMemoryIncrementalMetadataStore()
        store.upsert_records(job_id="job-1", job_run_id="run-1", records=sample_records)

        store.clear(job_id="job-1")

        assert store.get_processed_docs(job_id="job-1") == {}
        assert store.get_soft_deleted_doc_ids(job_id="job-1") == set()


class TestFileSystemIncrementalMetadataStore:
    def test_upsert_and_persist_records(self, *, tmp_path, sample_records):
        store = FileSystemIncrementalMetadataStore(backend_config={"base_dir": str(tmp_path), "lock_timeout": 5.0})

        store.upsert_records(job_id="job-1", job_run_id="run-1", records=sample_records)

        assert store.get_processed_docs(job_id="job-1") == {
            "doc-1": 1000,
            "doc-2": 2000,
        }

        records_file = tmp_path / "job-1" / "inc_process_metadata" / "incremental_metadata.json"
        assert records_file.exists()

        with open(records_file, encoding="utf-8") as file:
            payload = json.load(file)

        assert len(payload) == 2
        assert {item["doc_id"] for item in payload} == {"doc-1", "doc-2"}

    def test_mark_missing_docs_as_deleted(self, *, tmp_path, sample_records):
        store = FileSystemIncrementalMetadataStore(
            backend_config={"base_dir": str(tmp_path / "incremental_metadata"), "lock_timeout": 5.0}
        )
        store.upsert_records(job_id="job-1", job_run_id="run-1", records=sample_records)

        deleted_ids = store.mark_missing_docs_as_deleted(job_id="job-1", doc_ids=["doc-1"])

        assert deleted_ids == {"doc-2"}
        assert store.get_processed_docs(job_id="job-1") == {"doc-1": 1000}
        assert store.get_soft_deleted_doc_ids(job_id="job-1") == {"doc-2"}

    def test_delete_docs(self, *, tmp_path, sample_records):
        store = FileSystemIncrementalMetadataStore(
            backend_config={"base_dir": str(tmp_path / "incremental_metadata"), "lock_timeout": 5.0}
        )
        store.upsert_records(job_id="job-1", job_run_id="run-1", records=sample_records)

        store.delete_docs(job_id="job-1", doc_ids=["doc-1"])

        assert store.get_processed_docs(job_id="job-1") == {"doc-2": 2000}

    def test_clear(self, *, tmp_path, sample_records):
        store = FileSystemIncrementalMetadataStore(
            backend_config={"base_dir": str(tmp_path / "incremental_metadata"), "lock_timeout": 5.0}
        )
        store.upsert_records(job_id="job-1", job_run_id="run-1", records=sample_records)

        store.clear(job_id="job-1")

        assert store.get_processed_docs(job_id="job-1") == {}
        assert not (tmp_path / "incremental_metadata" / "job-1" / "incremental_metadata.json").exists()


class TestCreateIncrementalMetadataStoreWithFlowConfig:
    def test_create_file_system_store_with_flow_config(self, *, tmp_path):
        from datasift.utils.data.incremental_metadata_store import create_incremental_metadata_store

        flow_config = {
            "storage_type": "file_system",
            "config": {
                "base_dir": str(tmp_path / "custom_incremental"),
                "lock_timeout": 10.0,
            },
        }

        store = create_incremental_metadata_store(flow_config=flow_config)

        assert isinstance(store, FileSystemIncrementalMetadataStore)
        assert store._base_dir == tmp_path / "custom_incremental"
        assert store._lock_timeout == 10.0

    def test_create_inmemory_store_with_flow_config(self):
        from datasift.utils.data.incremental_metadata_store import create_incremental_metadata_store

        flow_config = {"storage_type": "in_memory", "config": {}}

        store = create_incremental_metadata_store(flow_config=flow_config)

        assert isinstance(store, InMemoryIncrementalMetadataStore)

    def test_create_store_with_invalid_backend(self):
        from datasift.utils.data.incremental_metadata_store import create_incremental_metadata_store

        flow_config = {"storage_type": "invalid_backend", "config": {}}

        with pytest.raises(ValueError, match="Unknown storage backend in flow config: invalid_backend"):
            create_incremental_metadata_store(flow_config=flow_config)

    def test_create_store_without_flow_config_uses_default(self):
        from datasift.utils.data.incremental_metadata_store import create_incremental_metadata_store

        store = create_incremental_metadata_store()

        assert store is not None
        assert isinstance(
            store,
            (InMemoryIncrementalMetadataStore, FileSystemIncrementalMetadataStore),
        )

    def test_flow_config_takes_precedence_over_legacy_config(self, *, tmp_path):
        from datasift.utils.data.incremental_metadata_store import create_incremental_metadata_store

        legacy_config = {"base_dir": str(tmp_path / "legacy")}
        flow_config = {
            "storage_type": "file_system",
            "config": {"base_dir": str(tmp_path / "flow_config")},
        }

        store = create_incremental_metadata_store(config=legacy_config, flow_config=flow_config)

        assert isinstance(store, FileSystemIncrementalMetadataStore)
        assert store._base_dir == tmp_path / "flow_config"
