    # Assisted by WCA@IBM
# Latest GenAI contribution: ibm/granite-8b-code-instruct
import json
import unittest
import uuid
from datetime import timedelta
from time import sleep
from unittest.mock import MagicMock, Mock, mock_open, patch
from uuid import uuid1

from common.exceptions.datasift_exceptions import DatasiftException
from common.models.session_info import create_session_info
from common.constants.constants import ExecutionStatus, Metrics
from common.util.job_tracker.model.models import JobStatsDto

from common.util.job_tracker.tracker.job_tracker import JobTracker
from core.orchestrator.orchestrator_factory import OrchestratorFactory

TOKEN_MANAGER = None
create_session_info(flow_id="flow1")
test_job_run_id = str(uuid1())
test_job_id = str(uuid1())


# Shared storage for all MockBaseDAO instances to ensure data persistence across DAL calls
_MOCK_STORAGE = {
    'job_stats': {},  # job_run_id -> JobRunStats
    'node_stats': {}  # (job_run_id, node_id) -> NodeStats
}


# Mock BaseDAO to avoid database dependencies in tests
class MockBaseDAO:
    """Mock implementation of BaseDAO for testing purposes with shared storage."""

    def __init__(self, model=None, session=None):
        self.model = model
        self.session = session
        # Use shared storage instead of instance storage
        self._storage = _MOCK_STORAGE

    def get_by_id(self, id):
        """Mock get_by_id method - retrieves from job_stats storage by job_run_id."""
        # The id parameter is actually the job_run_id for JobRunStats
        return self._storage['job_stats'].get(id)

    def add(self, obj):
        """Mock add method - stores in appropriate storage."""
        if hasattr(obj, 'job_run_id'):
            # This is a JobRunStats or NodeStats
            if hasattr(obj, 'node_id'):
                # NodeStats - use batch_id in key if present for micro-batching
                if hasattr(obj, 'batch_id') and obj.batch_id is not None:
                    # Batch record: use (job_run_id, node_id, batch_id) as key
                    key = (obj.job_run_id, obj.node_id, obj.batch_id)
                else:
                    # Non-batch record: use (job_run_id, node_id) as key
                    key = (obj.job_run_id, obj.node_id)
                self._storage['node_stats'][key] = obj
            else:
                # JobRunStats
                self._storage['job_stats'][obj.job_run_id] = obj
        elif hasattr(obj, 'id'):
            self._storage['job_stats'][obj.id] = obj
        return obj

    def upsert(self, obj):
        """Mock upsert method - same as add for our purposes."""
        return self.add(obj)

    def upsert_with_conflict(self, obj, index_elements, update_fields, where_clause=None):
        """Mock upsert_with_conflict"""
        return self.add(obj)

    def get_by_query(self, query):
        """Mock get_by_query method - returns all values from appropriate storage."""
        # Try to determine which storage to use based on model
        if self.model and hasattr(self.model, '__name__'):
            if 'NodeStats' in self.model.__name__:
                return list(self._storage['node_stats'].values())
        return list(self._storage['job_stats'].values())

    def get_first_by_query(self, query):
        """Mock get_first_by_query method - filters by job_run_id if present in query."""
        # Extract job_run_id from query if present
        query_str = str(query) if query is not None else ""

        # Check if query contains job_run_id filter
        if "job_run_id" in query_str and "==" in query_str:
            # Extract the job_run_id value from the query string
            # Format is typically: "JobRunStats.job_run_id == 'some-uuid'"
            import re
            match = re.search(r"job_run_id\s*==\s*['\"]([^'\"]+)['\"]", query_str)
            if match:
                job_run_id = match.group(1)
                # Return the specific job_stats for this job_run_id
                return self._storage['job_stats'].get(job_run_id)

        # Fallback to original behavior
        values = self.get_by_query(query)
        return values[0] if values else None

    def exists(self, condition):
        """Mock exists method - checks if any data exists matching condition."""
        # Check if condition is for batch records
        condition_str = str(condition) if condition else ""
        if "batch_id" in condition_str and "isnot" in condition_str:
            # Check for batch records (batch_id IS NOT NULL)
            return any(ns.batch_id is not None for ns in self._storage['node_stats'].values())
        return len(self._storage['job_stats']) > 0 or len(self._storage['node_stats']) > 0

    def delete_by_query(self, condition):
        """Mock delete_by_query method."""
        count = len(self._storage['job_stats']) + len(self._storage['node_stats'])
        self._storage['job_stats'].clear()
        self._storage['node_stats'].clear()
        return count

    def execute_with_session(self, fn):
        """Mock execute_with_session method."""
        mock_session = Mock()
        return fn(mock_session)

    def atomic_increment_fields(self, condition, increments, updates=None):
        """Mock atomic_increment_fields method - atomically updates fields."""
        # In the mock, we update all job_stats since we typically only have one per test
        for job_run_id, job_stats in self._storage['job_stats'].items():
            # Apply increments
            for field_name, increment_value in increments.items():
                if hasattr(job_stats, field_name):
                    current_value = getattr(job_stats, field_name) or 0
                    setattr(job_stats, field_name, current_value + increment_value)

            # Apply updates if provided
            if updates:
                for field_name, new_value in updates.items():
                    if hasattr(job_stats, field_name):
                        setattr(job_stats, field_name, new_value)

def clear_mock_storage():
    """Helper function to clear mock storage between tests."""
    _MOCK_STORAGE['job_stats'].clear()
    _MOCK_STORAGE['node_stats'].clear()

# Mock methods that don't exist in JobTracker but are expected by tests
class MockJobTrackerMethods:
    """Provides mock implementations of methods that tests expect but don't exist in JobTracker."""
    
    @staticmethod
    def _get_job_run(job_run_id: str):
        """Mock implementation of _get_job_run."""
        return {
            "metadata": {},
            "entity": {
                "job_run": {
                    "state": "Running",
                    "job_ref": "mock_job_id"
                }
            }
        }
    
    @staticmethod
    def _update_run_status(status, message=None):
        """Mock implementation of _update_run_status."""
        pass
    
    @staticmethod
    def _get_jobs():
        """Mock implementation of _get_jobs."""
        return {"results": []}
    
    @staticmethod
    def get_job_run_stats(job_run_id: str):
        """Mock implementation of get_job_run_stats."""
        return None
    
    @staticmethod
    def get_flow_execution_status(job_run_id: str, orchestrator_type: str = None):
        """Mock implementation of get_flow_execution_status."""
        return {"status": "RUNNING", "message": "Job is running"}


class TestJobTracker(unittest.TestCase):
    def setUp(self):
        # Clear mock storage before each test
        clear_mock_storage()
        self.tracker = JobTracker()
        # CRITICAL: Clear singleton cache for test isolation
        self.tracker.all_jobs.clear()
        # Clear orchestrator mapping for test isolation
        self.tracker._JobTracker__jobs_to_orchestrator.clear()
        self.original_get_job = self.tracker.get_job
        self.original_end_job = self.tracker.end_job
        # Generate unique job_run_id AND job_id for each test to avoid collisions
        global test_job_run_id, test_job_id
        test_job_run_id = str(uuid1())
        test_job_id = str(uuid1())
        
        # Add mock methods that don't exist in JobTracker but are expected by some tests
        #self.tracker._get_job_run = MockJobTrackerMethods._get_job_run
        #self.tracker._update_run_status = MockJobTrackerMethods._update_run_status
        #self.tracker._get_jobs = MockJobTrackerMethods._get_jobs
        #self.tracker.get_job_run_stats = MockJobTrackerMethods.get_job_run_stats
        #self.tracker.get_flow_execution_status = MockJobTrackerMethods.get_flow_execution_status

    def tearDown(self):
        self.tracker.get_job = self.original_get_job
        self.tracker.end_job = self.original_end_job
        # Clear mock storage after each test
        clear_mock_storage()
        # Clear singleton cache after each test
        self.tracker.all_jobs.clear()
        self.tracker._JobTracker__jobs_to_orchestrator.clear()
        # Reset any instance-level mocks to prevent contamination
        # Delete mock attributes to restore original methods from the class
        if hasattr(self.tracker, 'get_job_run_stats') and hasattr(self.tracker.get_job_run_stats, '_mock_name'):
            delattr(self.tracker, 'get_job_run_stats')
        if hasattr(self.tracker, 'store_job_stats') and hasattr(self.tracker.store_job_stats, '_mock_name'):
            delattr(self.tracker, 'store_job_stats')

    def test_start_job(self):
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1")
        self.tracker.start_tracking_job(orchestrator=orch, job_id="job1", job_run_id=test_job_run_id)
        self.assertIsNotNone(test_job_run_id)

        self.assertIn(test_job_run_id, self.tracker.all_jobs)
        self.assertEqual(self.tracker.all_jobs[test_job_run_id].status, ExecutionStatus.RUNNING)

    def test_update_doc_counts(self):
        operator_category = "Ingest"
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1")
        self.tracker.start_tracking_job(orchestrator=orch, job_id="job1", job_run_id=test_job_run_id)
        
        # update_doc_counts only handles TOTAL_DOCS (for Ingest), TOTAL_PAGES_CONVERTED, and DELETED_DOC_COUNT
        metadata = {
            Metrics.External.TOTAL_DOCS: 100, 
            Metrics.External.TOTAL_PAGES_CONVERTED: 75, 
            Metrics.External.DELETED_DOC_COUNT: 5
        }
        self.tracker.update_doc_counts(job_run_id=test_job_run_id, metadata=metadata, operator_category=operator_category)
        print("~~~~", self.tracker.all_jobs[test_job_run_id])

        self.assertEqual(self.tracker.all_jobs[test_job_run_id].total_docs, 100)
        self.assertEqual(self.tracker.all_jobs[test_job_run_id].total_pages_processed, 75)
        self.assertEqual(self.tracker.all_jobs[test_job_run_id].deleted_doc_count, 5)

    def test_end_job(self):
        # Extra cleanup to ensure test isolation
        clear_mock_storage()
        self.tracker.all_jobs.clear()
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1")
        self.tracker.start_tracking_job(orchestrator=orch, job_id="job1", job_run_id=test_job_run_id)
        sleep(1)
        self.tracker.end_job(job_run_id=test_job_run_id, job_log_path="/tmp/temp.log")
        self.assertEqual(self.tracker.all_jobs[test_job_run_id].status, ExecutionStatus.COMPLETED)
        self.assertGreater(self.tracker.all_jobs[test_job_run_id].duration, 0)

        # Attempt to trigger cancellation of completed job should result in no error
        self.tracker.request_cancel_job(job_run_id=test_job_run_id)

    def test_get_job(self):
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1")
        self.tracker.start_tracking_job(orchestrator=orch, job_id="job1", job_run_id=test_job_run_id)
        self.assertIsNotNone(self.tracker.get_job(job_run_id=test_job_run_id))
        self.assertIsNone(self.tracker.get_job(job_run_id='999999'))

    def test_cancel_job(self):
        operator_category = 'Ingest'
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1")
        self.tracker.start_tracking_job(orchestrator=orch, job_id="job1", job_run_id=test_job_run_id)
        self.assertIsNotNone(self.tracker.get_job(job_run_id=test_job_run_id))
        metadata = {Metrics.External.TOTAL_DOCS: 100, Metrics.External.PROCESSED_DOCS: 50}
        self.tracker.update_doc_counts(job_run_id=test_job_run_id, metadata=metadata, operator_category=operator_category)
        self.tracker.request_cancel_job(job_run_id=test_job_run_id)
        job_stats = self.tracker.get_job(job_run_id=test_job_run_id)
        self.assertIsNotNone(job_stats)
        self.assertEqual(job_stats.status, ExecutionStatus.CANCELING, "Job status should be changed to CANCELING")

        # Attempt to trigger cancellation 2nd time results in no-op
        self.tracker.request_cancel_job(job_run_id=test_job_run_id)
        job_stats = self.tracker.get_job(job_run_id=test_job_run_id)
        self.assertIsNotNone(job_stats)
        self.assertEqual(job_stats.status, ExecutionStatus.CANCELING, "Job status should still be CANCELING")

        self.tracker.end_job(job_run_id=test_job_run_id, job_log_path="/tmp/temp.log", status=ExecutionStatus.CANCELED)
        job_stats = self.tracker.get_job(test_job_run_id)
        self.assertIsNotNone(job_stats)
        self.assertEqual(job_stats.status, ExecutionStatus.CANCELED, "Job status should be changed to CANCELLED")

        # Attempt to trigger cancellation of already cancelled job results in no-op
        self.tracker.request_cancel_job(job_run_id=test_job_run_id)

    def test_cancel_job_without_stats(self):
        # Extra cleanup to ensure test isolation
        clear_mock_storage()
        self.tracker.all_jobs.clear()
        job_id = str(uuid1())  # Use unique job_id to avoid contamination
        
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1")
        
        job_run_id = str(uuid1())
        
        # request_cancel_job should raise an exception when job stats don't exist
        with self.assertRaises(DatasiftException) as context:
            self.tracker.request_cancel_job(job_run_id=job_run_id)
        
        self.assertIn(job_run_id, str(context.exception))

    def test_cancel_job_negative(self):
        test_job_run_id = str(uuid1())
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1", job_run_id=test_job_run_id)
        
        with self.assertRaises(DatasiftException) as context:
            self.tracker.request_cancel_job(job_run_id=test_job_run_id)
            self.assertIn(test_job_run_id, str(context.exception), f"Job run not found for ID: {test_job_run_id}")

        with self.assertRaises(DatasiftException) as context:
            self.tracker.end_job(job_run_id=test_job_run_id, job_log_path="/tmp/temp.log")
            self.assertIn(test_job_run_id, str(context.exception), f"Job run not found for ID: {test_job_run_id}")

    def test_cancel_job_without_job_id(self):
        test_job_run_id = str(uuid1())
        create_session_info()
        self.tracker.get_job = Mock(return_value=None)
        self.tracker._get_jobs = Mock(return_value={})
        with self.assertRaises(DatasiftException) as context:
            self.tracker.request_cancel_job(job_run_id=test_job_run_id)
            self.assertIn(f"Job run not found for ID: {test_job_run_id}", str(context.exception))  # NOSONAR

    def test_cancel_job_with_non_terminal_state(self):
        create_session_info()
        job_id = str(uuid1())
        job_run_id = str(uuid1())
        job_stats = JobStatsDto(
            job_id=job_id,
            job_run_id=job_run_id,
            status=ExecutionStatus.RUNNING
        )
        self.tracker.get_job = Mock(return_value=job_stats)
        # Mock store_job_stats to prevent contaminating _MOCK_STORAGE
        self.tracker.store_job_stats = Mock()

        result = self.tracker.request_cancel_job(job_run_id=job_run_id)
        
        # Verify the status was changed to CANCELING
        self.assertEqual(result.status, ExecutionStatus.CANCELING)
        # Verify store_job_stats was called to persist the change
        self.tracker.store_job_stats.assert_called_once()

    def test_cancel_job_with_status_different_in_persistent_store_and_jobs_framework(self):
        create_session_info()
        job_id = str(uuid1())
        job_run_id = str(uuid1())
        job_stats = JobStatsDto(
            job_id=job_id,
            job_run_id=job_run_id,
            status=ExecutionStatus.FAILED
        )
        self.tracker.get_job = Mock(return_value=job_stats)
        # Mock store_job_stats to prevent contaminating _MOCK_STORAGE
        self.tracker.store_job_stats = Mock()

        result = self.tracker.request_cancel_job(job_run_id=job_run_id)
        
        # Verify that terminal state (FAILED) is not changed
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        # Verify store_job_stats was not called since status didn't change
        self.tracker.store_job_stats.assert_not_called()

    @patch('common.util.job_tracker.storage.pickle_job_stats_store.PickleJobStatsStore.get_node_stats')
    @patch('common.util.job_tracker.storage.pickle_job_stats_store._get_job_id_for_job_run')
    @patch('common.util.job_tracker.storage.pickle_job_stats_store.PickleJobStatsStore.get_job_stats')
    def test_node_stats(self, mock_get_job_stats, mock_get_job_id_for_job_run, mock_get_node_stats):
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1")
        job_run_id = str(uuid1())
        job_id = str(uuid1())

        # Mock return values
        mock_get_job_id_for_job_run.return_value = job_id
        mock_get_job_stats.return_value = JobStatsDto(job_id=job_id, job_run_id=job_run_id, node_stats={})
        mock_get_node_stats.return_value = {
            str(i): {
                'node_id': uuid.uuid4(),
                'name': f'noop{i}',
                'time_taken': 200 * i,
                'col_names': ['col1', 'col2']
            } for i in range(5)
        }

        self.tracker.start_tracking_job(orchestrator=orch, job_id=job_id, job_run_id=job_run_id)
        for i in range(5):
            node_stats = {
                'node_id': uuid.uuid4(),
                'name': 'noop'+str(i),
                'time_taken': 200 * i,
                'node_status': ExecutionStatus.STARTING,
                'col_names': ['col1', 'col2']
            }
            self.tracker.update_node_stats(job_run_id=job_run_id, node_id=node_stats['node_id'], node_stats=node_stats)

        job_stats = self.tracker.get_job(job_run_id=job_run_id)
        self.assertIsNotNone(job_stats.node_stats)
        self.assertEqual(5, len(job_stats.node_stats))

    def test_singleton(self):
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1", job_run_id=test_job_run_id)
        
        for i in range(5):
            tracker = JobTracker()
            tracker.start_tracking_job(orchestrator=orch, job_id="job1", job_run_id=str(i))

        print(len(self.tracker.all_jobs))
        self.assertGreaterEqual(len(self.tracker.all_jobs), 5)

    def test_cancel_job_when_status_is_canceling(self):
        create_session_info(flow_id="flow1")
        self.tracker.get_job = Mock()
        self.tracker.end_job = Mock()
        # Mock job with CANCELING status
        job_stats_mock = Mock()
        job_stats_mock.status = ExecutionStatus.CANCELING
        self.tracker.get_job.return_value = job_stats_mock

        result = self.tracker.cancel_job_run_if_cancelling(job_run_id="job123", job_log_path="/tmp/temp.log")

        self.assertTrue(result)
        self.tracker.end_job.assert_called_once_with(
            job_run_id="job123",
            job_log_path='/tmp/temp.log',
            status=ExecutionStatus.CANCELED,
            message="Job run Canceled"
        )

    def test_not_cancel_job_when_status_is_not_canceling(self):
        create_session_info(flow_id="flow1")
        self.tracker.get_job = Mock()
        self.tracker.end_job = Mock()
        # Mock job with RUNNING status
        job_stats_mock = Mock()
        job_stats_mock.status = ExecutionStatus.RUNNING
        self.tracker.get_job.return_value = job_stats_mock

        result = self.tracker.cancel_job_run_if_cancelling(str(uuid1()), job_log_path="/tmp/temp.log")

        self.assertFalse(result)
        self.tracker.end_job.assert_not_called()


    def test_request_delete_job_run(self):
        orch = OrchestratorFactory.create_orchestrator()
        create_session_info(orchestrator=orch, flow_id="flow1", job_run_id=test_job_run_id)
        stat = Mock()
        stat.job_id = str(uuid1())
        self.tracker.start_tracking_job(orchestrator=orch, job_id=stat.job_id, job_run_id=test_job_run_id)
        self.tracker.request_delete_job_run(job_run_id=test_job_run_id)


class TestDocumentStatusDetermination(unittest.TestCase):
    def setUp(self):
        # Clear mock storage before each test
        clear_mock_storage()
        self.dag_nodes = [
            {"id": "node_ingest", "input_edges": [], "output_edges": [{"node_id_ref": "node_extract"}]},
            {"id": "node_extract", "input_edges": [{"node_id_ref": "node_ingest"}],
             "output_edges": [{"node_id_ref": "node_lang"}]},
            {"id": "node_lang", "input_edges": [{"node_id_ref": "node_extract"}],
             "output_edges": [{"node_id_ref": "node_branch"}]},
            {"id": "node_branch", "input_edges": [{"node_id_ref": "node_lang"}], "output_edges": [
                {"node_id_ref": "node_en"}, {"node_id_ref": "node_fr"}, {"node_id_ref": "node_ja"}
            ]},
            {"id": "node_en", "input_edges": [{"node_id_ref": "node_branch"}], "output_edges": []},
            {"id": "node_fr", "input_edges": [{"node_id_ref": "node_branch"}], "output_edges": []},
            {"id": "node_ja", "input_edges": [{"node_id_ref": "node_branch"}], "output_edges": []}
        ]

    def create_job_stats(self, total_docs, node_stats):
        return JobStatsDto(job_id="job1", job_run_id="run1", total_docs=total_docs, node_stats=node_stats)

    def test_mixed_branching_outcomes(self):
        docs = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        node_stats = {
            "node_ingest": {"id": "dbe97bf0-454b-4980-aaeb-7ac4b6c6355d", "name": "Ingest", "total_docs": docs},
            "node_en": {"id": "3b84b04c-bbb9-45cf-99e2-23b7a57d1f0b", "name": "English", "docs_completed": ["doc1", "doc2"], "failed_docs": ["doc3"], "skipped_docs": ["doc4", "doc5"]},
            "node_fr": {"id": "11a65301-8338-4185-8dd7-91c5e30863d2", "name": "French", "docs_completed": ["doc4"], "failed_docs": [], "skipped_docs": ["doc1", "doc2", "doc3","doc5"]},
            "node_ja": {"id": "6b1323c7-4533-4464-9819-00f1c611f1e3", "name": "Japanese", "docs_completed": ["doc3"], "failed_docs": [], "skipped_docs": ["doc1", "doc2", "doc4","doc5"]}
        }
        job_stats = self.create_job_stats(len(docs), node_stats)
        JobTracker().determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=self.dag_nodes)
        self.assertEqual(job_stats.processed_docs, 3)
        self.assertEqual(job_stats.failed_docs, 1)
        self.assertEqual(job_stats.skipped_docs, 1)

    def test_all_documents_skipped_in_all_branches(self):
        docs = ["doc1", "doc2"]
        node_stats = {
            "node_ingest": {"id": "dbe97bf0-454b-4980-aaeb-7ac4b6c6355d", "name": "Ingest", "total_docs": docs},
            "node_en": {"id": "3b84b04c-bbb9-45cf-99e2-23b7a57d1f0b", "name": "English", "docs_completed": [], "failed_docs": [], "skipped_docs": docs},
            "node_fr": {"id": "11a65301-8338-4185-8dd7-91c5e30863d2", "name": "French", "docs_completed": [], "failed_docs": [], "skipped_docs": docs},
            "node_ja": {"id": "6b1323c7-4533-4464-9819-00f1c611f1e3", "name": "Japanese", "docs_completed": [], "failed_docs": [], "skipped_docs": docs}
        }
        job_stats = self.create_job_stats(len(docs), node_stats)
        JobTracker().determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=self.dag_nodes)
        self.assertEqual(job_stats.processed_docs, 0)
        self.assertEqual(job_stats.failed_docs, 0)
        self.assertEqual(job_stats.skipped_docs, 2)

    def test_document_completed_in_one_branch_skipped_in_others(self):
        docs = ["doc1"]
        node_stats = {
            "node_ingest": {"id": "dbe97bf0-454b-4980-aaeb-7ac4b6c6355d", "name": "Ingest", "total_docs": docs},
            "node_en": {"id": "3b84b04c-bbb9-45cf-99e2-23b7a57d1f0b", "name": "English", "docs_completed": ["doc1"], "failed_docs": [], "skipped_docs": []},
            "node_fr": {"id": "11a65301-8338-4185-8dd7-91c5e30863d2", "name": "French", "docs_completed": [], "failed_docs": [], "skipped_docs": ["doc1"]},
            "node_ja": {"id": "6b1323c7-4533-4464-9819-00f1c611f1e3", "name": "Japanese", "docs_completed": [], "failed_docs": [], "skipped_docs": ["doc1"]}
        }
        job_stats = self.create_job_stats(len(docs), node_stats)
        JobTracker().determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=self.dag_nodes)
        self.assertEqual(job_stats.processed_docs, 1)
        self.assertEqual(job_stats.failed_docs, 0)
        self.assertEqual(job_stats.skipped_docs, 0)

    def test_document_failed_in_one_branch(self):
        docs = ["doc1"]
        node_stats = {
            "node_ingest": {"id": "dbe97bf0-454b-4980-aaeb-7ac4b6c6355d", "name": "Ingest", "total_docs": docs},
            "node_en": {"id": "3b84b04c-bbb9-45cf-99e2-23b7a57d1f0b", "name": "English", "docs_completed": [], "failed_docs": ["doc1"], "skipped_docs": []},
            "node_fr": {"id": "11a65301-8338-4185-8dd7-91c5e30863d2", "name": "French", "docs_completed": [], "failed_docs": [], "skipped_docs": ["doc1"]},
            "node_ja": {"id": "6b1323c7-4533-4464-9819-00f1c611f1e3", "name": "Japanese", "docs_completed": [], "failed_docs": [], "skipped_docs": ["doc1"]}
        }
        job_stats = self.create_job_stats(len(docs), node_stats)
        JobTracker().determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=self.dag_nodes)
        self.assertEqual(job_stats.processed_docs, 0)
        self.assertEqual(job_stats.failed_docs, 1)
        self.assertEqual(job_stats.skipped_docs, 0)

    def test_create_running_job_stats(self):
        flow_id = 'flow1'
        job_stats_dto: JobStatsDto = JobStatsDto.create_running_job_stats(
            job_id=test_job_id,
            job_run_id=test_job_run_id,
            flow_id=flow_id
        )
        assert isinstance(job_stats_dto, JobStatsDto)
        assert job_stats_dto.job_id == test_job_id
        assert job_stats_dto.job_run_id == test_job_run_id
        assert job_stats_dto.flow_id == flow_id
        assert job_stats_dto.status == ExecutionStatus.RUNNING

    def test_multiple_failures_across_nodes(self):
        """Test that failures in multiple nodes are correctly marked"""
        docs = ["doc1", "doc2", "doc3", "doc4"]
        node_stats = {
            "node_ingest": {"id": "dbe97bf0-454b-4980-aaeb-7ac4b6c6355d", "name": "Ingest", "total_docs": docs},
            "node_extract": {"id": "208f04ed-27b9-47b3-b95e-136805bde8bf", "name": "Extract", "failed_docs": ["doc2"]},
            "node_en": {"id": "3b84b04c-bbb9-45cf-99e2-23b7a57d1f0b", "name": "English", "docs_completed": ["doc1"], "failed_docs": ["doc3"], "skipped_docs": []},
            "node_fr": {"id": "11a65301-8338-4185-8dd7-91c5e30863d2", "name": "French", "docs_completed": ["doc4"], "failed_docs": [], "skipped_docs": []},
            "node_ja": {"id": "6b1323c7-4533-4464-9819-00f1c611f1e3", "name": "Japanese", "docs_completed": [], "failed_docs": [], "skipped_docs": []}
        }
        job_stats = self.create_job_stats(len(docs), node_stats)
        JobTracker().determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=self.dag_nodes)
        self.assertEqual(job_stats.failed_docs, 2)  # doc2, doc3
        self.assertEqual(job_stats.processed_docs, 2)  # doc1, doc4
        self.assertEqual(job_stats.skipped_docs, 0)

    def test_completed_docs_dont_override_failed_status(self):
        """Test that completed status doesn't override failed status"""
        docs = ["doc1", "doc2"]
        node_stats = {
            "node_ingest": {"id": "dbe97bf0-454b-4980-aaeb-7ac4b6c6355d", "name": "Ingest", "total_docs": docs},
            "node_extract": {"id": "208f04ed-27b9-47b3-b95e-136805bde8bf", "name": "Extract", "failed_docs": ["doc2"]},
            "node_en": {"id": "3b84b04c-bbb9-45cf-99e2-23b7a57d1f0b", "name": "English", "docs_completed": ["doc1", "doc2"], "failed_docs": [], "skipped_docs": []},
            "node_fr": {"id": "11a65301-8338-4185-8dd7-91c5e30863d2", "name": "French", "docs_completed": [], "failed_docs": [], "skipped_docs": []},
            "node_ja": {"id": "6b1323c7-4533-4464-9819-00f1c611f1e3", "name": "Japanese", "docs_completed": [], "failed_docs": [], "skipped_docs": []}
        }
        job_stats = self.create_job_stats(len(docs), node_stats)
        JobTracker().determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=self.dag_nodes)
        self.assertEqual(job_stats.failed_docs, 1)  # doc2 remains failed
        self.assertEqual(job_stats.processed_docs, 1)  # only doc1

    def test_none_values_in_node_stats(self):
        """Test handling of None values in failed_docs, docs_completed, and total_docs"""
        docs = ["doc1", "doc2"]
        node_stats = {
            "node_ingest": {"id": "dbe97bf0-454b-4980-aaeb-7ac4b6c6355d", "name": "Ingest", "total_docs": docs},
            "node_en": {"id": "3b84b04c-bbb9-45cf-99e2-23b7a57d1f0b", "name": "English", "docs_completed": None, "failed_docs": None, "skipped_docs": []},
            "node_fr": {"id": "11a65301-8338-4185-8dd7-91c5e30863d2", "name": "French", "docs_completed": ["doc1"], "failed_docs": [], "skipped_docs": []},
            "node_ja": {"id": "6b1323c7-4533-4464-9819-00f1c611f1e3", "name": "Japanese", "docs_completed": [], "failed_docs": [], "skipped_docs": []}
        }
        job_stats = self.create_job_stats(len(docs), node_stats)
        JobTracker().determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=self.dag_nodes)
        self.assertEqual(job_stats.processed_docs, 1)  # doc1
        self.assertEqual(job_stats.failed_docs, 0)
        self.assertEqual(job_stats.skipped_docs, 1)  # doc2

    def test_missing_ingest_node(self):
        """Test behavior when ingest node is missing from node_stats"""
        docs = ["doc1", "doc2"]
        node_stats = {
            # Missing ingest node
            "node_en": {"id": "3b84b04c-bbb9-45cf-99e2-23b7a57d1f0b", "name": "English", "docs_completed": ["doc1"], "failed_docs": [], "skipped_docs": []},
            "node_fr": {"id": "11a65301-8338-4185-8dd7-91c5e30863d2", "name": "French", "docs_completed": [], "failed_docs": [], "skipped_docs": []},
            "node_ja": {"id": "6b1323c7-4533-4464-9819-00f1c611f1e3", "name": "Japanese", "docs_completed": [], "failed_docs": [], "skipped_docs": []}
        }
        job_stats = self.create_job_stats(len(docs), node_stats)
        JobTracker().determine_and_update_final_documents_count(job_stats=job_stats, dag_nodes=self.dag_nodes)
        self.assertEqual(job_stats.processed_docs, 1)  # doc1
        self.assertEqual(job_stats.skipped_docs, 0)  # No skipped since ingest node missing

if __name__ == "__main__":
    unittest.main()
