"""Unit tests for JobManagementService."""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus
from docpipe.core.job_management.application.services.job_management_service import JobManagementService
from docpipe.exceptions.docpipe_exceptions import (
    FlowInvalidDataException,
    FlowNotFoundException,
    FlowValidationException,
)


class DummyConfigModel:
    """Simple stand-in for job_run configuration models."""

    def __init__(self, data: dict):
        self._data = data
        self.user_id = data.get("user_id")
        self.metadata = data.get("metadata", {})

    def model_dump(self, *, exclude_none: bool = True) -> dict:
        return {k: v for k, v in self._data.items() if not exclude_none or v is not None}


class DummyJobRun:
    """Simple stand-in for job run request payload."""

    def __init__(self, configuration=None):
        self.configuration = configuration


class DummyJob:
    """Simple stand-in for job request payload."""

    def __init__(self, *, asset_ref: str | None, name: str | None = None, configuration: dict | None = None):
        self.asset_ref = asset_ref
        self.name = name
        self.configuration = configuration or {}


class DummyRequestBody:
    """Simple stand-in for JobsAPIExecuteModel."""

    def __init__(self, *, job, job_run):
        self.entity = Mock(job=job, job_run=job_run)


class DummyJobRunItem:
    """Simple stand-in for job run list items."""

    def __init__(self, payload: dict):
        self.payload = payload

    def model_dump(self, *, include: set[str]):
        return {key: self.payload[key] for key in include if key in self.payload}


class TestJobManagementService:
    """Test JobManagementService."""

    def setup_method(self) -> None:
        self.job_stats_service = Mock()
        self.job_run_manager = Mock()
        self.flow_service = Mock()
        self.executor = Mock()
        self.service = JobManagementService(
            job_stats_service=self.job_stats_service,
            job_run_manager=self.job_run_manager,
            flow_service=self.flow_service,
            executor=self.executor,
        )

    def test_create_job_run_from_request_raises_when_asset_ref_missing(self):
        """Test request parsing fails when asset_ref is missing."""
        request_body = DummyRequestBody(job=DummyJob(asset_ref=None), job_run=DummyJobRun())

        with pytest.raises(FlowNotFoundException, match=r"entity\.job\.asset_ref is required"):
            self.service.create_job_run_from_request(request_body=request_body)

    def test_create_job_run_from_request_merges_job_and_job_run_config(self):
        """Test request parsing merges job and job run configuration."""
        request_body = DummyRequestBody(
            job=DummyJob(asset_ref="flow-1", name="My Flow", configuration={"from_job": "value"}),
            job_run=DummyJobRun(
                configuration=DummyConfigModel(
                    {
                        "from_run": "override",
                        "user_id": "user-1",
                        "metadata": {"source": "api"},
                    }
                )
            ),
        )
        self.service._create_job_run = Mock(return_value={"job_run_id": "run-1"})

        result = self.service.create_job_run_from_request(request_body=request_body)

        assert result == {"job_run_id": "run-1"}
        self.service._create_job_run.assert_called_once_with(
            flow_id="flow-1",
            flow_name="My Flow",
            flow_config={
                "from_job": "value",
                "from_run": "override",
                "user_id": "user-1",
                "metadata": {"source": "api"},
            },
            user_id="user-1",
            metadata={"source": "api"},
        )

    @patch("docpipe.core.assets.flows.domain.models.authoring_flow.AuthoringFlow.from_dict")
    @patch("docpipe.core.assets.flows.application.services.authoring_compiler.AuthoringCompiler.compile")
    @patch("docpipe.core.job_management.application.services.job_management_service.get_session_info")
    def test_create_job_run_compiles_authoring_flow(
        self,
        mock_get_session_info,
        mock_compile,
        mock_from_dict,
    ):
        """Test _create_job_run compiles authoring flows and submits async execution."""
        flow = Mock(job_id="job-123", definition={DocpipeConstants.FLOW_NAME: "Flow", "flow": []})
        self.flow_service.get_flow.return_value = flow
        self.job_run_manager.create_job_run.return_value = {
            DocpipeConstants.JOB_ID: "job-123",
            DocpipeConstants.JOB_RUN_ID: "run-123",
        }
        mock_compile.return_value = {"dag": []}
        mock_get_session_info.return_value = Mock()

        result = self.service._create_job_run(flow_id="flow-1", flow_name="Flow", flow_config={"k": "v"})

        assert result[DocpipeConstants.JOB_RUN_ID] == "run-123"
        self.job_stats_service.start_tracking_job.assert_called_once()
        self.executor.submit.assert_called_once()
        submit_args = self.executor.submit.call_args.args
        assert submit_args[0] == self.service._execute_flow_async
        assert submit_args[3] == "run-123"
        assert submit_args[4] == {"dag": []}
        assert submit_args[5][DocpipeConstants.JOB_ID] == "job-123"
        mock_from_dict.assert_called_once_with(data=flow.definition)

    @patch("docpipe.utils.orchestration.elyra_converter.ElyraConverter.transform_elyra_to_internal")
    @patch("docpipe.core.job_management.application.services.job_management_service.get_session_info")
    def test_create_job_run_transforms_elyra_flow(self, mock_get_session_info, mock_transform):
        """Test _create_job_run transforms Elyra flows and submits async execution."""
        flow = Mock(job_id=None, definition={"doc_type": "pipeline"})
        self.flow_service.get_flow.return_value = flow
        self.job_run_manager.create_job_run.return_value = {
            DocpipeConstants.JOB_ID: "flow-1",
            DocpipeConstants.JOB_RUN_ID: "run-123",
        }
        mock_transform.return_value = {"dag": []}
        mock_get_session_info.return_value = Mock()

        result = self.service._create_job_run(flow_id="flow-1", flow_name="Flow", flow_config={})

        assert result[DocpipeConstants.JOB_ID] == "flow-1"
        mock_transform.assert_called_once_with(elyra_json=flow.definition, flow_id="flow-1")
        self.executor.submit.assert_called_once()

    def test_create_job_run_raises_for_unknown_flow_format(self):
        """Test _create_job_run rejects unknown flow formats."""
        flow = Mock(job_id=None, definition={"unexpected": True})
        self.flow_service.get_flow.return_value = flow
        self.job_run_manager.create_job_run.return_value = {
            DocpipeConstants.JOB_ID: "flow-1",
            DocpipeConstants.JOB_RUN_ID: "run-123",
        }

        with pytest.raises(FlowInvalidDataException, match="unknown format"):
            self.service._create_job_run(flow_id="flow-1", flow_name="Flow", flow_config={})

    def test_get_job_run_status_returns_job_stats(self):
        """Test get_job_run_status delegates to job stats service."""
        expected = Mock()
        self.job_stats_service.get_job_run_stats.return_value = expected

        result = self.service.get_job_run_status(job_run_id="run-1")

        assert result is expected
        self.job_stats_service.get_job_run_stats.assert_called_once_with(job_run_id="run-1")

    def test_cancel_job_run_requests_cancel_and_notifies_manager(self):
        """Test cancel_job_run updates services."""
        self.service.cancel_job_run(job_run_id="run-1")

        self.job_stats_service.request_cancel_job.assert_called_once_with(job_run_id="run-1")
        self.job_run_manager.cancel_job_run.assert_called_once_with(job_run_id="run-1")

    def test_delete_job_run_requests_delete_and_notifies_manager(self):
        """Test delete_job_run updates services."""
        self.service.delete_job_run(job_run_id="run-1")

        self.job_stats_service.request_delete_job_run.assert_called_once_with(job_run_id="run-1")
        self.job_run_manager.delete_job_run.assert_called_once_with(job_run_id="run-1")

    def test_list_job_runs_formats_response(self):
        """Test list_job_runs transforms results into API payload."""
        self.job_stats_service.list_job_runs.return_value = [
            DummyJobRunItem(
                {
                    DocpipeConstants.JOB_RUN_ID: "run-1",
                    DocpipeConstants.JOB_ID: "job-1",
                    DocpipeConstants.STATUS: ExecutionStatus.COMPLETED.value,
                    DocpipeConstants.MESSAGE: "done",
                }
            )
        ]

        result = self.service.list_job_runs(job_id="job-1", status=ExecutionStatus.COMPLETED, limit=10)

        assert result["count"] == 1
        assert result["total"] == 1
        assert result["list"][0][DocpipeConstants.JOB_RUN_ID] == "run-1"
        self.job_stats_service.list_job_runs.assert_called_once_with(
            job_id="job-1", status=ExecutionStatus.COMPLETED, limit=10
        )

    @patch("docpipe.core.job_management.application.services.job_management_service.set_session_info")
    @patch("docpipe.core.orchestration.orchestrator_factory.OrchestratorFactory.create_orchestrator")
    @patch("docpipe.core.orchestration.flow_executor.FlowExecutor")
    def test_execute_flow_async_defaults_micro_batching_when_missing(
        self,
        mock_flow_executor_class,
        mock_create_orchestrator,
        mock_set_session_info,
    ):
        """Test async execution defaults micro-batching to true when missing."""
        mock_orchestrator = Mock()
        mock_create_orchestrator.return_value = mock_orchestrator
        mock_flow_executor = Mock()
        mock_flow_executor_class.return_value = mock_flow_executor

        self.service._execute_flow_async(
            session_info=Mock(),
            job_id="job-1",
            job_run_id="run-1",
            flow_definition={"dag": []},
            flow_config={"custom": "value"},
        )

        mock_set_session_info.assert_called_once()
        execute_kwargs = mock_flow_executor.execute.call_args.kwargs
        assert execute_kwargs["params"][DocpipeConstants.ENABLE_MICRO_BATCHING] is True
        assert execute_kwargs["params"]["custom"] == "value"

    @patch("docpipe.core.job_management.application.services.job_management_service.set_session_info")
    @patch("docpipe.core.orchestration.orchestrator_factory.OrchestratorFactory.create_orchestrator")
    @patch("docpipe.core.orchestration.flow_executor.FlowExecutor")
    def test_execute_flow_async_respects_explicit_micro_batching_value(
        self,
        mock_flow_executor_class,
        mock_create_orchestrator,
        mock_set_session_info,
    ):
        """Test async execution preserves explicit micro-batching config from flow_config."""
        mock_orchestrator = Mock()
        mock_create_orchestrator.return_value = mock_orchestrator
        mock_flow_executor = Mock()
        mock_flow_executor_class.return_value = mock_flow_executor

        self.service._execute_flow_async(
            session_info=Mock(),
            job_id="job-1",
            job_run_id="run-1",
            flow_definition={"dag": []},
            flow_config={DocpipeConstants.ENABLE_MICRO_BATCHING: False},
        )

        mock_set_session_info.assert_called_once()
        execute_kwargs = mock_flow_executor.execute.call_args.kwargs
        assert execute_kwargs["params"][DocpipeConstants.ENABLE_MICRO_BATCHING] is False

    @patch("docpipe.core.job_management.application.services.job_management_service.set_session_info")
    @patch("docpipe.core.orchestration.orchestrator_factory.OrchestratorFactory.create_orchestrator")
    @patch("docpipe.core.orchestration.flow_executor.FlowExecutor")
    def test_execute_flow_async_respects_flow_definition_global_config_micro_batching(
        self,
        mock_flow_executor_class,
        mock_create_orchestrator,
        mock_set_session_info,
    ):
        """Test async execution does not override explicit enable_micro_batching in flow definition."""
        mock_orchestrator = Mock()
        mock_create_orchestrator.return_value = mock_orchestrator
        mock_flow_executor = Mock()
        mock_flow_executor_class.return_value = mock_flow_executor

        self.service._execute_flow_async(
            session_info=Mock(),
            job_id="job-1",
            job_run_id="run-1",
            flow_definition={"dag": [], "global_config": {DocpipeConstants.ENABLE_MICRO_BATCHING: False}},
            flow_config={},
        )

        mock_set_session_info.assert_called_once()
        execute_kwargs = mock_flow_executor.execute.call_args.kwargs
        assert DocpipeConstants.ENABLE_MICRO_BATCHING not in execute_kwargs["params"]

    def test_serialize_validation_alerts_handles_dicts_and_unknown_types(self):
        """Test validation alert serialization across supported input shapes."""
        alerts = [
            {"node_name": "node-1", "operator": "noop", "message": "problem", "extra": "ignored"},
            "plain string alert",
        ]

        result = self.service._serialize_validation_alerts(alerts)

        assert result[0] == {"node_name": "node-1", "operator": "noop", "message": "problem"}
        assert result[1] == {"message": "plain string alert"}

    def test_serialize_validation_alerts_handles_model_dump_and_to_dict(self):
        """Test validation alert serialization for model-like objects and to_dict objects."""

        class ModelAlert:
            def model_dump(self, *, exclude_none: bool = True):
                return {"node_name": "node-2", "operator": "extract", "message": "warning"}

        class DictAlert:
            def to_dict(self):
                return {"node_name": "node-3", "operator": "chunk", "message": "notice"}

        result = self.service._serialize_validation_alerts([ModelAlert(), DictAlert()])

        assert result[0] == {"node_name": "node-2", "operator": "extract", "message": "warning"}
        assert result[1] == {"node_name": "node-3", "operator": "chunk", "message": "notice"}

    def test_format_validation_error_message_includes_errors_and_warnings(self):
        """Test validation error message formatting includes serialized details."""
        exc = FlowValidationException(
            message="validation failed",
            errors=[{"node_name": "node-1", "operator": "noop", "message": "error"}],
            warnings=[{"node_name": "node-2", "operator": "extract", "message": "warning"}],
        )

        result = self.service._format_validation_error_message(exc)

        assert "Flow validation error: validation failed" in result
        assert '"node_name": "node-1"' in result
        assert '"node_name": "node-2"' in result

    def test_build_detailed_error_message_adds_exception_type(self):
        """Test detailed error message includes exception type when missing."""
        result = self.service._build_detailed_error_message(ValueError("bad input"))

        assert result == "ValueError: bad input"

    def test_build_detailed_error_message_keeps_existing_exception_type(self):
        """Test detailed error message does not duplicate exception type text."""
        result = self.service._build_detailed_error_message(ValueError("ValueError: already prefixed"))

        assert result == "ValueError: already prefixed"

    def test_build_detailed_error_message_appends_structured_error_details(self):
        """Test detailed error message appends pydantic-style error details."""

        class ErrorWithDetails(Exception):
            def __init__(self):
                super().__init__("validation failed")
                self.errors = [
                    {"loc": ["body", "field"], "msg": "missing"},
                    {"loc": ["body", "other"], "msg": "invalid"},
                ]

        result = self.service._build_detailed_error_message(ErrorWithDetails())

        assert "ErrorWithDetails: validation failed" in result
        assert "body -> field: missing" in result
        assert "body -> other: invalid" in result

    @patch("docpipe.core.job_management.application.services.job_management_service.set_session_info")
    @patch("docpipe.core.orchestration.orchestrator_factory.OrchestratorFactory.create_orchestrator")
    @patch("docpipe.core.orchestration.flow_executor.FlowExecutor")
    def test_execute_flow_async_handles_validation_exception(
        self,
        mock_flow_executor_class,
        mock_create_orchestrator,
        mock_set_session_info,
    ):
        """Test async execution handles FlowValidationException and marks the run failed."""
        mock_orchestrator = Mock()
        mock_create_orchestrator.return_value = mock_orchestrator
        validation_exc = FlowValidationException(message="validation failed", errors=[{"message": "bad flow"}])
        mock_flow_executor = Mock()
        mock_flow_executor.execute.side_effect = validation_exc
        mock_flow_executor_class.return_value = mock_flow_executor

        self.service._execute_flow_async(
            session_info=Mock(),
            job_id="job-1",
            job_run_id="run-1",
            flow_definition={"dag": []},
            flow_config={},
        )

        mock_set_session_info.assert_called_once()
        self.job_run_manager.update_job_run_status.assert_called_once()
        self.job_stats_service.end_job.assert_called_once()
        update_kwargs = self.job_run_manager.update_job_run_status.call_args.kwargs
        assert update_kwargs["status"] == ExecutionStatus.FAILED.value

    @patch("docpipe.core.job_management.application.services.job_management_service.set_session_info")
    @patch("docpipe.core.orchestration.orchestrator_factory.OrchestratorFactory.create_orchestrator")
    @patch("docpipe.core.orchestration.flow_executor.FlowExecutor")
    def test_execute_flow_async_handles_generic_exception(
        self,
        mock_flow_executor_class,
        mock_create_orchestrator,
        mock_set_session_info,
    ):
        """Test async execution handles generic exceptions and marks the run failed."""
        mock_orchestrator = Mock()
        mock_create_orchestrator.return_value = mock_orchestrator
        mock_flow_executor = Mock()
        mock_flow_executor.execute.side_effect = RuntimeError("boom")
        mock_flow_executor_class.return_value = mock_flow_executor

        self.service._execute_flow_async(
            session_info=Mock(),
            job_id="job-1",
            job_run_id="run-1",
            flow_definition={"dag": []},
            flow_config={},
        )

        mock_set_session_info.assert_called_once()
        self.job_run_manager.update_job_run_status.assert_called_once()
        self.job_stats_service.end_job.assert_called_once()
        end_kwargs = self.job_stats_service.end_job.call_args.kwargs
        assert end_kwargs["status"] == ExecutionStatus.FAILED.value
        assert "RuntimeError: boom" in end_kwargs["job_run_stats"][DocpipeConstants.MESSAGE]

    def test_shutdown_closes_executor(self):
        """Test shutdown closes the executor."""
        self.service.shutdown()

        self.executor.shutdown.assert_called_once_with(wait=True)
