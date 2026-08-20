"""
Unit tests for WorkPoolAdapter.

All Prefect server calls (get_client, run_deployment, wait_for_flow_run) are
patched at the module level so the tests run with no live Prefect server.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pyarrow as pa
import pytest

from docpipe.core.orchestration.batch_manager import BatchInfo
from docpipe.core.orchestration.prefect.adapters.work_pool_adapter import WorkPoolAdapter
from docpipe.core.orchestration.prefect.domain.models import (
    BatchStorageType,
)
from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROCESS_CONFIG = {
    "type": "process",
    "work_pool_name": "test-pool",
    "deployment_name": "test-deployment",
}


def _mock_engine() -> Mock:
    engine = Mock()
    engine.logger = Mock()
    return engine


def _build_adapter(extra: dict | None = None) -> WorkPoolAdapter:
    """Construct WorkPoolAdapter with connectivity mocked out."""
    config = {**_PROCESS_CONFIG, **(extra or {})}
    with (
        patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
        patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
    ):
        return WorkPoolAdapter(
            work_pool_config=config,
            prefect_engine=_mock_engine(),
            batch_manager=Mock(),
        )


def _table(n: int = 2) -> pa.Table:
    return pa.table({"id": list(range(n)), "content": [f"doc_{i}" for i in range(n)]})


def _batch(num: int = 0) -> BatchInfo:
    return BatchInfo(batch_id=f"bid-{num}", batch_num=num, table=_table())


# ---------------------------------------------------------------------------
# __init__ — validation
# ---------------------------------------------------------------------------


class TestWorkPoolAdapterInit:
    def test_raises_when_work_pool_name_missing(self):
        with pytest.raises(ValueError, match="work_pool_name"):
            with (
                patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
                patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
            ):
                WorkPoolAdapter(
                    work_pool_config={"type": "process"},
                    prefect_engine=_mock_engine(),
                    batch_manager=Mock(),
                )

    def test_raises_when_local_storage_missing_path(self):
        config = {**_PROCESS_CONFIG, "batch_storage": {"type": "local"}}
        with pytest.raises(ValueError, match=r"batch_storage\.path"):
            with (
                patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
                patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
            ):
                WorkPoolAdapter(work_pool_config=config, prefect_engine=_mock_engine(), batch_manager=Mock())

    def test_raises_when_s3_bucket_missing(self):
        config = {
            **_PROCESS_CONFIG,
            "batch_storage": {"type": "s3", "access_key_id": "k", "secret_access_key": "s"},  # pragma: allowlist secret
        }
        with pytest.raises(ValueError, match=r"batch_storage\.bucket"):
            with (
                patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
                patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
            ):
                WorkPoolAdapter(work_pool_config=config, prefect_engine=_mock_engine(), batch_manager=Mock())

    def test_raises_when_s3_credentials_missing(self):
        config = {**_PROCESS_CONFIG, "batch_storage": {"type": "s3", "bucket": "b"}}
        with pytest.raises(ValueError, match="S3 credentials"):
            with (
                patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
                patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
            ):
                WorkPoolAdapter(work_pool_config=config, prefect_engine=_mock_engine(), batch_manager=Mock())

    def test_defaults_storage_type_to_inline(self):
        assert _build_adapter().batch_storage_type == BatchStorageType.INLINE

    def test_custom_deployment_name_stored(self):
        assert _build_adapter({"deployment_name": "my-deploy"}).deployment_name == "my-deploy"

    def test_s3_credential_aliases_accepted(self):
        config = {
            **_PROCESS_CONFIG,
            "batch_storage": {
                "type": "s3",
                "bucket": "b",
                "access_key": "ak",
                "secret_key": "sk",  # pragma: allowlist secret
            },
        }
        with (
            patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
            patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
        ):
            adapter = WorkPoolAdapter(work_pool_config=config, prefect_engine=_mock_engine(), batch_manager=Mock())
        assert adapter.s3_access_key == "ak"
        assert adapter.s3_secret_key == "sk"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# _validate_prefect_connection
# ---------------------------------------------------------------------------


class TestValidatePrefectConnection:
    def _client_ctx(self, client: Mock) -> MagicMock:
        ctx = MagicMock()
        ctx.__enter__ = Mock(return_value=client)
        ctx.__exit__ = Mock(return_value=False)
        return ctx

    def test_raises_on_health_check_error(self):
        client = Mock()
        client.api_healthcheck.return_value = "server error"
        with patch.object(WorkPoolAdapter, "_ensure_deployment_exists"):
            with patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.get_client",
                return_value=self._client_ctx(client),
            ):
                with pytest.raises(ValueError, match="health check failed"):
                    WorkPoolAdapter(
                        work_pool_config=_PROCESS_CONFIG,
                        prefect_engine=_mock_engine(),
                        batch_manager=Mock(),
                    )

    def test_raises_on_connection_exception(self):
        ctx = MagicMock()
        ctx.__enter__ = Mock(side_effect=OSError("refused"))
        ctx.__exit__ = Mock(return_value=False)
        with patch.object(WorkPoolAdapter, "_ensure_deployment_exists"):
            with patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.get_client",
                return_value=ctx,
            ):
                with pytest.raises(ValueError, match="Cannot connect"):
                    WorkPoolAdapter(
                        work_pool_config=_PROCESS_CONFIG,
                        prefect_engine=_mock_engine(),
                        batch_manager=Mock(),
                    )

    def test_passes_with_healthy_server(self):
        client = Mock()
        client.api_healthcheck.return_value = None
        with patch.object(WorkPoolAdapter, "_ensure_deployment_exists"):
            with patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.get_client",
                return_value=self._client_ctx(client),
            ):
                adapter = WorkPoolAdapter(
                    work_pool_config=_PROCESS_CONFIG,
                    prefect_engine=_mock_engine(),
                    batch_manager=Mock(),
                )
        assert adapter.work_pool_name == "test-pool"


# ---------------------------------------------------------------------------
# _transfer_batch — dispatch
# ---------------------------------------------------------------------------


class TestTransferBatchDispatch:
    def test_inline_by_default(self):
        adapter = _build_adapter()
        with patch.object(adapter, "_transfer_batch_inline", return_value={"type": "inline"}) as m:
            result = adapter._transfer_batch(batch_table=_table(), batch_num=0, job_run_id="jr1")
        m.assert_called_once()
        assert result == {"type": "inline"}

    def test_local_storage_type(self):
        adapter = _build_adapter()
        adapter.batch_storage_type = BatchStorageType.LOCAL
        with patch.object(adapter, "_transfer_batch_local", return_value={"type": "local"}) as m:
            result = adapter._transfer_batch(batch_table=_table(), batch_num=0, job_run_id="jr1")
        m.assert_called_once()
        assert result == {"type": "local"}

    def test_s3_storage_type(self):
        adapter = _build_adapter()
        adapter.batch_storage_type = BatchStorageType.S3
        with patch.object(adapter, "_transfer_batch_s3", return_value={"type": "s3"}) as m:
            result = adapter._transfer_batch(batch_table=_table(), batch_num=0, job_run_id="jr1")
        m.assert_called_once()
        assert result == {"type": "s3"}


# ---------------------------------------------------------------------------
# _transfer_batch_inline
# ---------------------------------------------------------------------------


class TestTransferBatchInline:
    def test_returns_inline_descriptor(self):
        adapter = _build_adapter()
        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.get_inline_size_limit",
            return_value=1_000_000,
        ):
            result = adapter._transfer_batch_inline(batch_table=_table(2), batch_num=0, job_run_id="jr1")
        assert result["type"] == BatchStorageType.INLINE.value
        assert result["data"]["row_count"] == 2

    def test_raises_when_exceeds_size_limit(self):
        adapter = _build_adapter()
        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.get_inline_size_limit",
            return_value=1,
        ):
            with pytest.raises(FlowExecutionFailedException, match="exceeding Prefect"):
                adapter._transfer_batch_inline(batch_table=_table(2), batch_num=0, job_run_id="jr1")

    def test_base64_encodes_binary_columns(self):
        import base64

        adapter = _build_adapter()
        tbl = pa.table({"id": [1], "blob": pa.array([b"hello"], type=pa.binary())})
        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.get_inline_size_limit",
            return_value=1_000_000,
        ):
            result = adapter._transfer_batch_inline(batch_table=tbl, batch_num=0, job_run_id="jr1")
        assert result["data"]["data"][0]["blob"] == base64.b64encode(b"hello").decode()

    def test_warns_near_limit(self):
        adapter = _build_adapter()
        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.get_inline_size_limit",
                return_value=1_000_000,
            ),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.INLINE_SIZE_WARNING_THRESHOLD",
                0.0,  # always warn
            ),
        ):
            adapter._transfer_batch_inline(batch_table=_table(2), batch_num=0, job_run_id="jr1")
        adapter.prefect_engine.logger.warning.assert_called()


# ---------------------------------------------------------------------------
# _transfer_batch_local
# ---------------------------------------------------------------------------


class TestTransferBatchLocal:
    def test_writes_parquet_returns_descriptor(self, tmp_path):
        adapter = _build_adapter()
        adapter.batch_storage_path = str(tmp_path)
        tbl = _table(3)
        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.replace_memmap_paths_combined",
            return_value=tbl,
        ):
            result = adapter._transfer_batch_local(batch_table=tbl, batch_num=1, job_run_id="job-abc")
        assert result["type"] == BatchStorageType.LOCAL.value
        assert "batch-1.parquet" in result["ref"]
        assert (tmp_path / "job-abc" / "batch-1.parquet").exists()

    def test_raises_on_write_failure(self, tmp_path):
        adapter = _build_adapter()
        adapter.batch_storage_path = str(tmp_path)
        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.replace_memmap_paths_combined",
                return_value=_table(),
            ),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.pq.write_table",
                side_effect=OSError("disk full"),
            ),
        ):
            with pytest.raises(FlowExecutionFailedException, match="disk full"):
                adapter._transfer_batch_local(batch_table=_table(), batch_num=0, job_run_id="jr1")


# ---------------------------------------------------------------------------
# _transfer_batch_s3
# ---------------------------------------------------------------------------


class TestTransferBatchS3:
    def _s3_adapter(self) -> WorkPoolAdapter:
        adapter = _build_adapter()
        adapter.batch_storage_type = BatchStorageType.S3
        adapter.batch_storage_bucket = "my-bucket"
        adapter.batch_storage_prefix = "tmp/"
        adapter.s3_access_key = "ak"
        adapter.s3_secret_key = "sk"  # pragma: allowlist secret
        adapter.s3_endpoint_url = None
        adapter.s3_region = None
        return adapter

    def test_returns_s3_descriptor(self):
        adapter = self._s3_adapter()
        tbl = _table(2)
        with (
            patch.object(adapter, "_create_s3_filesystem", return_value=Mock()),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.replace_memmap_paths_combined",
                return_value=tbl,
            ),
            patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.pq.write_table"),
        ):
            result = adapter._transfer_batch_s3(batch_table=tbl, batch_num=2, job_run_id="jr1")
        assert result["type"] == BatchStorageType.S3.value
        assert result["bucket"] == "my-bucket"
        assert "batch-2.parquet" in result["ref"]

    def test_raises_on_s3_failure(self):
        adapter = self._s3_adapter()
        with (
            patch.object(adapter, "_create_s3_filesystem", return_value=Mock()),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.replace_memmap_paths_combined",
                return_value=_table(),
            ),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.pq.write_table",
                side_effect=RuntimeError("s3 err"),
            ),
        ):
            with pytest.raises(FlowExecutionFailedException, match="s3 err"):
                adapter._transfer_batch_s3(batch_table=_table(), batch_num=0, job_run_id="jr1")


# ---------------------------------------------------------------------------
# _create_s3_filesystem
# ---------------------------------------------------------------------------


class TestCreateS3Filesystem:
    def test_builds_without_region_or_endpoint(self):
        adapter = _build_adapter()
        adapter.s3_access_key = "ak"
        adapter.s3_secret_key = "sk"  # pragma: allowlist secret
        adapter.s3_region = None
        adapter.s3_endpoint_url = None
        mock_cls = Mock(return_value=Mock())
        with patch("pyarrow.fs.S3FileSystem", mock_cls):
            adapter._create_s3_filesystem()
        mock_cls.assert_called_once_with(access_key="ak", secret_key="sk")  # pragma: allowlist secret

    def test_builds_with_region_and_endpoint(self):
        adapter = _build_adapter()
        adapter.s3_access_key = "ak"
        adapter.s3_secret_key = "sk"  # pragma: allowlist secret
        adapter.s3_region = "us-east-1"
        adapter.s3_endpoint_url = "http://minio:9000"
        mock_cls = Mock(return_value=Mock())
        with patch("pyarrow.fs.S3FileSystem", mock_cls):
            adapter._create_s3_filesystem()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["region"] == "us-east-1"
        assert call_kwargs["endpoint_override"] == "http://minio:9000"


# ---------------------------------------------------------------------------
# _cleanup_batch_storage
# ---------------------------------------------------------------------------


class TestCleanupBatchStorage:
    def test_local_removes_directory(self, tmp_path):
        adapter = _build_adapter()
        adapter.batch_storage_type = BatchStorageType.LOCAL
        adapter.batch_storage_path = str(tmp_path)
        d = tmp_path / "job-abc"
        d.mkdir()
        (d / "batch-0.parquet").write_bytes(b"x")
        adapter._cleanup_batch_storage(job_run_id="job-abc")
        assert not d.exists()

    def test_local_missing_directory_does_not_raise(self, tmp_path):
        adapter = _build_adapter()
        adapter.batch_storage_type = BatchStorageType.LOCAL
        adapter.batch_storage_path = str(tmp_path)
        adapter._cleanup_batch_storage(job_run_id="nonexistent")

    def test_local_logs_warning_on_rmtree_error(self, tmp_path):
        adapter = _build_adapter()
        adapter.batch_storage_type = BatchStorageType.LOCAL
        adapter.batch_storage_path = str(tmp_path)
        d = tmp_path / "job-err"
        d.mkdir()
        with patch("shutil.rmtree", side_effect=OSError("perm denied")):
            adapter._cleanup_batch_storage(job_run_id="job-err")
        adapter.prefect_engine.logger.warning.assert_called()

    def test_s3_logs_info(self):
        adapter = _build_adapter()
        adapter.batch_storage_type = BatchStorageType.S3
        adapter.batch_storage_bucket = "b"
        adapter.batch_storage_prefix = "tmp/"
        adapter._cleanup_batch_storage(job_run_id="j1")
        adapter.prefect_engine.logger.info.assert_called()

    def test_inline_is_noop(self):
        adapter = _build_adapter()
        adapter.batch_storage_type = BatchStorageType.INLINE
        adapter._cleanup_batch_storage(job_run_id="j1")  # must not raise


# ---------------------------------------------------------------------------
# _raise_failure (static)
# ---------------------------------------------------------------------------


class TestRaiseFailure:
    def test_raises_with_batch_details(self):
        with pytest.raises(FlowExecutionFailedException, match="Batch 0"):
            WorkPoolAdapter._raise_failure(
                failed_info=[{"batch_num": 0, "run_id": "rid", "message": "timeout"}],
                completed_count=1,
                total_count=2,
            )

    def test_message_contains_counts(self):
        with pytest.raises(FlowExecutionFailedException) as exc:
            WorkPoolAdapter._raise_failure(
                failed_info=[{"batch_num": 2, "run_id": "r", "message": "err"}],
                completed_count=3,
                total_count=5,
            )
        msg = str(exc.value)
        assert "Completed: 3" in msg
        assert "Total: 5" in msg


# ---------------------------------------------------------------------------
# get_strategy_name
# ---------------------------------------------------------------------------


class TestGetStrategyName:
    def test_contains_work_pool_and_type(self):
        adapter = _build_adapter()
        name = adapter.get_strategy_name()
        assert "work-pool" in name
        assert adapter.work_pool_type in name


# ---------------------------------------------------------------------------
# _resolve_job_management_config_path (static)
# ---------------------------------------------------------------------------


class TestResolveConfigPath:
    def test_uses_env_var(self, tmp_path):
        cfg = tmp_path / "cfg.yaml"
        with patch.dict("os.environ", {"DOCPIPE_CONFIG_PATH": str(cfg)}):
            result = WorkPoolAdapter._resolve_job_management_config_path()
        assert result == cfg.resolve()

    def test_falls_back_to_default(self):
        import os

        env = {k: v for k, v in os.environ.items() if k != "DOCPIPE_CONFIG_PATH"}
        with patch.dict("os.environ", env, clear=True):
            result = WorkPoolAdapter._resolve_job_management_config_path()
        assert result.name == "docling-pipelines-config.yaml"


# ---------------------------------------------------------------------------
# _get_effective_job_management_env
# ---------------------------------------------------------------------------


class TestGetEffectiveJobManagementEnv:
    def test_includes_factory_env(self):
        adapter = _build_adapter()
        mock_factory = Mock()
        mock_factory.resolve_worker_env.return_value = {"MY_VAR": "val"}
        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.JobManagementFactory.from_default_sources",
                return_value=mock_factory,
            ),
            patch.object(adapter, "_resolve_job_management_config_path", return_value=Path("/no/config.yaml")),
        ):
            result = adapter._get_effective_job_management_env()
        assert "MY_VAR" in result

    def test_tolerates_factory_exception(self):
        adapter = _build_adapter()
        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.JobManagementFactory.from_default_sources",
                side_effect=RuntimeError("factory down"),
            ),
            patch.object(adapter, "_resolve_job_management_config_path", return_value=Path("/no/config.yaml")),
        ):
            result = adapter._get_effective_job_management_env()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# _build_container_env
# ---------------------------------------------------------------------------


class TestBuildContainerEnv:
    def test_fills_required_defaults(self):
        adapter = _build_adapter()
        with patch.object(adapter, "_get_effective_job_management_env", return_value={}):
            result = adapter._build_container_env(base_env={}, deployment_path="/app")
        for key in ("PREFECT_API_URL", "PREFECT_MODE", "PYTHONPATH"):
            assert key in result

    def test_does_not_override_existing_keys(self):
        adapter = _build_adapter()
        base = {"PREFECT_API_URL": "http://custom:4200/api"}
        with patch.object(adapter, "_get_effective_job_management_env", return_value={}):
            result = adapter._build_container_env(base_env=base, deployment_path=None)
        assert result["PREFECT_API_URL"] == "http://custom:4200/api"

    def test_deployment_path_none_uses_cwd(self):
        adapter = _build_adapter()
        with patch.object(adapter, "_get_effective_job_management_env", return_value={}):
            result = adapter._build_container_env(base_env={}, deployment_path=None)
        assert result["PYTHONPATH"] == str(Path.cwd())


# ---------------------------------------------------------------------------
# _build_job_variables
# ---------------------------------------------------------------------------


class TestBuildJobVariables:
    def test_returns_none_for_unknown_config_type(self):
        adapter = _build_adapter()
        adapter.work_pool_runtime_config = Mock(spec=[])
        assert adapter._build_job_variables() is None

    def test_process_config_returns_env_dict(self):
        from docpipe.core.orchestration.prefect.config.work_pool_config import ProcessWorkPoolConfig

        adapter = _build_adapter()
        adapter.work_pool_runtime_config = ProcessWorkPoolConfig(env={})
        with patch.object(adapter, "_build_container_env", return_value={"K": "V"}):
            result = adapter._build_job_variables()
        assert result == {"env": {"K": "V"}}

    def test_docker_config_returns_image_and_env(self):
        from docpipe.core.orchestration.prefect.config.work_pool_config import DockerWorkPoolConfig

        adapter = _build_adapter()
        adapter.work_pool_runtime_config = DockerWorkPoolConfig(image="my-img:latest", env={})
        with patch.object(adapter, "_build_container_env", return_value={"K": "V"}):
            result = adapter._build_job_variables()
        assert result["image"] == "my-img:latest"
        assert result["env"] == {"K": "V"}

    def test_docker_config_includes_networks_when_set(self):
        from docpipe.core.orchestration.prefect.config.work_pool_config import DockerWorkPoolConfig

        adapter = _build_adapter()
        adapter.work_pool_runtime_config = DockerWorkPoolConfig(image="img", networks=["net1"])
        with patch.object(adapter, "_build_container_env", return_value={}):
            result = adapter._build_job_variables()
        assert result["networks"] == ["net1"]


# ---------------------------------------------------------------------------
# _classify_flow_run_result
# ---------------------------------------------------------------------------


class TestClassifyFlowRunResult:
    def _fr(self, state=None) -> Mock:
        fr = Mock()
        fr.id = "fr-001"
        fr.state = state
        return fr

    def test_exception_result_appends_failure(self):
        adapter = _build_adapter()
        failed: list[dict] = []
        count = adapter._classify_flow_run_result(
            batch_num=0,
            flow_run=self._fr(),
            result=ValueError("boom"),
            completed_count=0,
            failed_info=failed,
            job_run_id="jr",
        )
        assert len(failed) == 1
        assert count == 0

    def _real_flow_run(self, state):  # type: ignore[return]
        """Return a real FlowRun instance so isinstance(result, FlowRun) passes."""
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        return _FlowRun.model_construct(flow_id=uuid4(), state=state)

    def test_completed_state_increments_count(self):
        adapter = _build_adapter()
        state = Mock()
        state.is_completed.return_value = True
        state.is_failed.return_value = False
        state.is_crashed.return_value = False
        state.is_cancelled.return_value = False
        result = self._real_flow_run(state)
        failed: list[dict] = []
        count = adapter._classify_flow_run_result(
            batch_num=0, flow_run=self._fr(state), result=result, completed_count=2, failed_info=failed, job_run_id="jr"
        )
        assert count == 3
        assert failed == []

    def test_failed_state_appends_failure(self):
        adapter = _build_adapter()
        state = Mock()
        state.is_completed.return_value = False
        state.is_failed.return_value = True
        state.is_crashed.return_value = False
        state.is_cancelled.return_value = False
        state.message = "task failed"
        result = self._real_flow_run(state)
        failed: list[dict] = []
        count = adapter._classify_flow_run_result(
            batch_num=1, flow_run=self._fr(state), result=result, completed_count=0, failed_info=failed, job_run_id="jr"
        )
        assert len(failed) == 1
        assert count == 0

    def test_none_state_returns_count_unchanged(self):
        adapter = _build_adapter()
        # A plain non-FlowRun result triggers the early-return path — count stays the same
        count = adapter._classify_flow_run_result(
            batch_num=0,
            flow_run=self._fr(),
            result="not-a-flow-run",
            completed_count=5,
            failed_info=[],
            job_run_id="jr",
        )
        assert count == 5

    def test_cancelled_state_logs_warning(self):
        adapter = _build_adapter()
        state = Mock()
        state.is_completed.return_value = False
        state.is_failed.return_value = False
        state.is_crashed.return_value = False
        state.is_cancelled.return_value = True
        result = self._real_flow_run(state)
        adapter._classify_flow_run_result(
            batch_num=0, flow_run=self._fr(state), result=result, completed_count=0, failed_info=[], job_run_id="jr"
        )
        adapter.prefect_engine.logger.warning.assert_called()


# ---------------------------------------------------------------------------
# execute_batches (public entry point)
# ---------------------------------------------------------------------------


class TestExecuteBatches:
    def test_calls_async_pipeline_and_cleanup(self):
        adapter = _build_adapter()
        batch = _batch(0)

        async_mock = AsyncMock()
        with (
            patch.object(adapter, "_execute_pipelined_batches_async", async_mock),
            patch.object(adapter, "_cleanup_batch_storage") as cleanup_mock,
        ):
            adapter.execute_batches(batches=[batch], op_flow=[], global_config={}, job_run_id="jr1")

        async_mock.assert_awaited_once()
        cleanup_mock.assert_called_once_with(job_run_id="jr1")

    def test_logs_summary_on_success(self):
        adapter = _build_adapter()
        with (
            patch.object(adapter, "_execute_pipelined_batches_async", AsyncMock()),
            patch.object(adapter, "_cleanup_batch_storage"),
        ):
            adapter.execute_batches(batches=[_batch()], op_flow=[], global_config={}, job_run_id="jr1")
        adapter.prefect_engine.logger.info.assert_called()


# ---------------------------------------------------------------------------
# _wait_for_flow_runs_async (async — happy path and failure path)
# ---------------------------------------------------------------------------


class TestWaitForFlowRunsAsync:
    def _mock_flow_run(self):
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        fr = _FlowRun.model_construct(flow_id=uuid4())
        fr.id = fr.flow_id
        return fr

    @pytest.mark.asyncio
    async def test_happy_path_no_failures(self):
        adapter = _build_adapter()
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        fr = self._mock_flow_run()
        completed_state = Mock()
        completed_state.is_completed.return_value = True
        completed_state.is_failed.return_value = False
        completed_state.is_crashed.return_value = False
        completed_state.is_cancelled.return_value = False
        completed_fr = _FlowRun.model_construct(flow_id=uuid4(), state=completed_state)
        completed_fr.id = completed_fr.flow_id

        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.wait_for_flow_run",
            AsyncMock(return_value=completed_fr),
        ):
            # Should not raise
            await adapter._wait_for_flow_runs_async(flow_runs=[fr], job_run_id="jr1")

    @pytest.mark.asyncio
    async def test_failure_raises_flow_execution_exception(self):
        adapter = _build_adapter()
        fr = self._mock_flow_run()

        failed_state = Mock()
        failed_state.is_completed.return_value = False
        failed_state.is_failed.return_value = True
        failed_state.is_crashed.return_value = False
        failed_state.is_cancelled.return_value = False
        failed_state.message = "worker crashed"

        from prefect.client.schemas.objects import FlowRun as _FlowRun

        failed_fr = _FlowRun.model_construct(flow_id=uuid4(), state=failed_state)
        failed_fr.id = failed_fr.flow_id

        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.wait_for_flow_run",
                AsyncMock(return_value=failed_fr),
            ),
            patch.object(adapter, "_cancel_remaining_runs_async", AsyncMock()),
        ):
            with pytest.raises(FlowExecutionFailedException):
                await adapter._wait_for_flow_runs_async(flow_runs=[fr], job_run_id="jr1")

    @pytest.mark.asyncio
    async def test_unexpected_exception_is_reraised(self):
        """Non-Exception gather errors propagate as-is; Exception results become FlowExecutionFailedException."""
        adapter = _build_adapter()
        fr = self._mock_flow_run()

        # wait_for_flow_run raising an Exception gets gathered as a result — ends up in failed_info
        # and triggers FlowExecutionFailedException via _raise_failure
        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.wait_for_flow_run",
                AsyncMock(side_effect=RuntimeError("connection lost")),
            ),
            patch.object(adapter, "_cancel_remaining_runs_async", AsyncMock()),
        ):
            with pytest.raises(FlowExecutionFailedException):
                await adapter._wait_for_flow_runs_async(flow_runs=[fr], job_run_id="jr1")


# ---------------------------------------------------------------------------
# _cancel_single_run (async)
# ---------------------------------------------------------------------------


class TestCancelSingleRun:
    def _mock_fr(self):
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        fr = _FlowRun.model_construct(flow_id=uuid4())
        fr.id = fr.flow_id
        return fr

    @pytest.mark.asyncio
    async def test_cancels_non_terminal_run(self):
        adapter = _build_adapter()
        fr = self._mock_fr()

        current = Mock()
        current.state = Mock()
        current.state.is_final.return_value = False

        client = AsyncMock()
        client.read_flow_run = AsyncMock(return_value=current)
        client.set_flow_run_state = AsyncMock()

        result = await adapter._cancel_single_run(client=client, flow_run=fr, job_run_id="jr1")
        assert result == fr.id
        client.set_flow_run_state.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_terminal_run(self):
        adapter = _build_adapter()
        fr = self._mock_fr()

        current = Mock()
        current.state = Mock()
        current.state.is_final.return_value = True

        client = AsyncMock()
        client.read_flow_run = AsyncMock(return_value=current)

        result = await adapter._cancel_single_run(client=client, flow_run=fr, job_run_id="jr1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        adapter = _build_adapter()
        fr = self._mock_fr()

        client = AsyncMock()
        client.read_flow_run = AsyncMock(side_effect=RuntimeError("server err"))

        result = await adapter._cancel_single_run(client=client, flow_run=fr, job_run_id="jr1")
        assert result is None
        adapter.prefect_engine.logger.warning.assert_called()


# ---------------------------------------------------------------------------
# _cancel_remaining_runs (sync version)
# ---------------------------------------------------------------------------


class TestCancelRemainingRunsSync:
    def _mock_fr(self):
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        fr = _FlowRun.model_construct(flow_id=uuid4())
        fr.id = fr.flow_id
        return fr

    def test_cancels_each_run_via_sync_client(self):
        adapter = _build_adapter()
        fr = self._mock_fr()

        sync_client = Mock()
        sync_client.set_flow_run_state = Mock()
        ctx = MagicMock()
        ctx.__enter__ = Mock(return_value=sync_client)
        ctx.__exit__ = Mock(return_value=False)

        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.get_client",
            return_value=ctx,
        ):
            adapter._cancel_remaining_runs(flow_runs=[fr], failed_run_id="fr-failed", job_run_id="jr1")

        sync_client.set_flow_run_state.assert_called_once()

    def test_logs_warning_on_cancel_error(self):
        adapter = _build_adapter()
        fr = self._mock_fr()

        sync_client = Mock()
        sync_client.set_flow_run_state = Mock(side_effect=RuntimeError("cancel failed"))
        ctx = MagicMock()
        ctx.__enter__ = Mock(return_value=sync_client)
        ctx.__exit__ = Mock(return_value=False)

        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.get_client",
            return_value=ctx,
        ):
            # Should not raise
            adapter._cancel_remaining_runs(flow_runs=[fr], failed_run_id="fr-failed", job_run_id="jr1")

        adapter.prefect_engine.logger.warning.assert_called()


# ---------------------------------------------------------------------------
# _cancel_remaining_runs_async
# ---------------------------------------------------------------------------


class TestCancelRemainingRunsAsync:
    @pytest.mark.asyncio
    async def test_cancels_and_waits_for_pending(self):
        adapter = _build_adapter()
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        fr = _FlowRun.model_construct(flow_id=uuid4())
        fr.id = fr.flow_id

        async_ctx = MagicMock()
        mock_client = AsyncMock()
        async_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        async_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.get_client",
                return_value=async_ctx,
            ),
            patch.object(adapter, "_cancel_single_run", AsyncMock(return_value=fr.id)),
            patch.object(adapter, "_wait_for_pending_termination", AsyncMock()),
        ):
            await adapter._cancel_remaining_runs_async(flow_runs=[fr], job_run_id="jr1")


# ---------------------------------------------------------------------------
# _ensure_deployment_exists — deployment already exists path
# ---------------------------------------------------------------------------


class TestEnsureDeploymentExists:
    def test_returns_early_when_deployment_already_exists(self):
        adapter = _build_adapter()

        existing = Mock()
        existing.id = "dep-001"
        # get_client(sync_client=True) is called bare (no context manager) inside _ensure_deployment_exists
        sync_client = Mock()
        sync_client.read_deployment_by_name = Mock(return_value=existing)

        mock_subflow = Mock()
        mock_subflow.name = "docpipe-batch-subflow"

        with (
            # Patch the local import inside _ensure_deployment_exists: "from prefect import get_client"
            patch("prefect.get_client", return_value=sync_client),
            patch(
                "docpipe.core.orchestration.prefect.batch_subflow.batch_subflow",
                mock_subflow,
                create=True,
            ),
        ):
            adapter._ensure_deployment_exists()

        adapter.prefect_engine.logger.info.assert_called()

    def test_raises_runtime_error_on_create_failure(self):
        adapter = _build_adapter()

        sync_client = Mock()
        sync_client.read_deployment_by_name = Mock(side_effect=Exception("not found"))
        sync_client.read_flow_by_name = Mock(side_effect=[Exception("not found"), Mock(id="fid")])
        sync_client.create_flow = Mock(return_value="flow-id-001")
        sync_client.create_deployment = Mock(side_effect=RuntimeError("work pool missing"))

        mock_subflow = Mock()
        mock_subflow.name = "docpipe-batch-subflow"

        with (
            patch("prefect.get_client", return_value=sync_client),
            patch(
                "docpipe.core.orchestration.prefect.batch_subflow.batch_subflow",
                mock_subflow,
                create=True,
            ),
        ):
            with pytest.raises(RuntimeError, match="Failed to create deployment"):
                adapter._ensure_deployment_exists()


# ---------------------------------------------------------------------------
# _wait_for_pending_termination (async)
# ---------------------------------------------------------------------------


class TestWaitForPendingTermination:
    @pytest.mark.asyncio
    async def test_empty_pending_runs_exits_immediately(self):
        """Empty list: while loop never executes — covers entry + info log."""
        adapter = _build_adapter()
        client = AsyncMock()
        # Should complete instantly with no iterations
        await adapter._wait_for_pending_termination(client=client, pending_runs=[], job_run_id="jr1")
        adapter.prefect_engine.logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_timeout_logs_warning(self):
        """Covers sleep+read+update (lines 740-743) then timeout branch (734-738).

        Clock sequence:
          call 0 → start_wait = 0.0            (line 732)
          call 1 → loop check = 0.0  → proceed (line 734, first iteration)
          call 2 → loop check = 100.0 → timeout (line 734, second iteration)
        """
        from uuid import UUID

        adapter = _build_adapter()
        run_id = UUID("00000000-0000-0000-0000-000000000002")

        # Run stays non-terminal so the list stays populated after line 743
        non_terminal = Mock()
        non_terminal.id = run_id
        non_terminal.state = Mock()
        non_terminal.state.is_final.return_value = False

        client = AsyncMock()
        client.read_flow_runs = AsyncMock(return_value=[non_terminal])

        mock_loop = Mock()
        mock_loop.time.side_effect = [0.0, 0.0, 100.0]  # start, first check (pass), second check (timeout)

        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.asyncio.sleep",
                AsyncMock(),
            ),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.asyncio.get_event_loop",
                return_value=mock_loop,
            ),
        ):
            await adapter._wait_for_pending_termination(client=client, pending_runs=[run_id], job_run_id="jr1")

        adapter.prefect_engine.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_poll_exception_is_swallowed(self):
        """Covers the except branch (lines 744-747): poll error is logged, not raised.

        Clock sequence: start=0.0, first-check=0.0 (proceed), second-check=100.0 (timeout).
        """
        adapter = _build_adapter()
        run_id = "uuid-003"

        client = AsyncMock()
        client.read_flow_runs = AsyncMock(side_effect=RuntimeError("poll error"))

        mock_loop = Mock()
        mock_loop.time.side_effect = [0.0, 0.0, 100.0]

        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.asyncio.sleep",
                AsyncMock(),
            ),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.asyncio.get_event_loop",
                return_value=mock_loop,
            ),
        ):
            # Must not raise
            await adapter._wait_for_pending_termination(client=client, pending_runs=[run_id], job_run_id="jr1")

        adapter.prefect_engine.logger.warning.assert_called()


# ---------------------------------------------------------------------------
# _ensure_deployment_exists — process worker creation path
# ---------------------------------------------------------------------------


class TestEnsureDeploymentExistsCreate:
    def _setup_create_mock(self, work_pool_type="process"):
        """Return (adapter, sync_client, mock_subflow) ready for _ensure_deployment_exists."""
        extra = {"type": work_pool_type}
        if work_pool_type == "docker":
            extra["image"] = "my-img:latest"
        adapter = _build_adapter(extra)

        sync_client = Mock()
        sync_client.read_deployment_by_name = Mock(side_effect=Exception("not found"))
        flow_obj = Mock()
        flow_obj.id = "fid-001"
        sync_client.read_flow_by_name = Mock(return_value=flow_obj)
        sync_client.create_deployment = Mock(return_value="dep-id-001")

        mock_subflow = Mock()
        mock_subflow.name = "docpipe-batch-subflow"

        return adapter, sync_client, mock_subflow

    def test_creates_deployment_for_process_pool(self):
        adapter, sync_client, mock_subflow = self._setup_create_mock("process")

        with (
            patch("prefect.get_client", return_value=sync_client),
            patch(
                "docpipe.core.orchestration.prefect.batch_subflow.batch_subflow",
                mock_subflow,
                create=True,
            ),
            patch.object(adapter, "_build_job_variables", return_value=None),
        ):
            adapter._ensure_deployment_exists()

        sync_client.create_deployment.assert_called_once()
        adapter.prefect_engine.logger.info.assert_called()

    def test_creates_deployment_for_docker_pool(self):
        adapter, sync_client, mock_subflow = self._setup_create_mock("docker")

        with (
            patch("prefect.get_client", return_value=sync_client),
            patch(
                "docpipe.core.orchestration.prefect.batch_subflow.batch_subflow",
                mock_subflow,
                create=True,
            ),
            patch.object(adapter, "_build_job_variables", return_value={"image": "my-img:latest", "env": {}}),
        ):
            adapter._ensure_deployment_exists()

        sync_client.create_deployment.assert_called_once()

    def test_registers_flow_when_not_found(self):
        """Covers the flow-registration branch (flow not yet in Prefect Server)."""
        adapter, sync_client, mock_subflow = self._setup_create_mock("process")

        flow_obj = Mock()
        flow_obj.id = "fid-after-create"
        # First call raises (not found), second call returns the registered flow
        sync_client.read_flow_by_name = Mock(side_effect=[Exception("not found"), flow_obj])
        sync_client.create_flow = Mock(return_value="fid-after-create")

        with (
            patch("prefect.get_client", return_value=sync_client),
            patch(
                "docpipe.core.orchestration.prefect.batch_subflow.batch_subflow",
                mock_subflow,
                create=True,
            ),
            patch.object(adapter, "_build_job_variables", return_value=None),
        ):
            adapter._ensure_deployment_exists()

        sync_client.create_flow.assert_called_once()
        sync_client.create_deployment.assert_called_once()


# ---------------------------------------------------------------------------
# _wait_for_flow_runs (sync wrapper — line 601)
# ---------------------------------------------------------------------------


class TestWaitForFlowRunsSync:
    def test_delegates_to_async_impl(self):
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        adapter = _build_adapter()
        fr = _FlowRun.model_construct(flow_id=uuid4())
        fr.id = fr.flow_id

        with patch.object(adapter, "_wait_for_flow_runs_async", AsyncMock()):
            adapter._wait_for_flow_runs(flow_runs=[fr], job_run_id="jr1")


# ---------------------------------------------------------------------------
# _classify_flow_run_result — crashed branch (lines 634-646)
# ---------------------------------------------------------------------------


class TestClassifyFlowRunResultCrashed:
    def test_crashed_state_appends_failure(self):
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        adapter = _build_adapter()
        state = Mock()
        state.is_completed.return_value = False
        state.is_failed.return_value = False
        state.is_crashed.return_value = True
        state.is_cancelled.return_value = False
        state.message = "OOM"
        _fid = uuid4()
        result = _FlowRun.model_construct(flow_id=_fid, state=state)
        result.id = _fid
        fr = Mock()
        fr.id = _fid
        failed: list[dict] = []
        count = adapter._classify_flow_run_result(
            batch_num=3, flow_run=fr, result=result, completed_count=0, failed_info=failed, job_run_id="jr"
        )
        assert len(failed) == 1
        assert "CRASHED" in failed[0]["message"] or failed[0]["message"] == "OOM"
        assert count == 0


# ---------------------------------------------------------------------------
# _wait_for_flow_runs_async — outer except branch (lines 694-700)
# ---------------------------------------------------------------------------


class TestWaitForFlowRunsAsyncOuterExcept:
    @pytest.mark.asyncio
    async def test_non_flow_exception_logs_and_reraises(self):
        """Covers lines 694-700: asyncio.gather itself raises (not return_exceptions path)."""
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        adapter = _build_adapter()
        fr = _FlowRun.model_construct(flow_id=uuid4())
        fr.id = fr.flow_id

        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.asyncio.gather",
            AsyncMock(side_effect=MemoryError("OOM")),
        ):
            with pytest.raises(MemoryError):
                await adapter._wait_for_flow_runs_async(flow_runs=[fr], job_run_id="jr1")

        adapter.prefect_engine.logger.error.assert_called()


# ---------------------------------------------------------------------------
# _cancel_remaining_runs_async — no pending runs path (lines 762-765)
# ---------------------------------------------------------------------------


class TestCancelRemainingRunsAsyncNoPending:
    @pytest.mark.asyncio
    async def test_no_pending_skips_wait(self):
        """When _cancel_single_run returns None for all runs, _wait_for_pending_termination is not called."""
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        adapter = _build_adapter()
        fr = _FlowRun.model_construct(flow_id=uuid4())
        fr.id = fr.flow_id

        async_ctx = MagicMock()
        mock_client = AsyncMock()
        async_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        async_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.get_client",
                return_value=async_ctx,
            ),
            patch.object(adapter, "_cancel_single_run", AsyncMock(return_value=None)),
            patch.object(adapter, "_wait_for_pending_termination", AsyncMock()) as wait_mock,
        ):
            await adapter._cancel_remaining_runs_async(flow_runs=[fr], job_run_id="jr1")

        wait_mock.assert_not_called()


# ---------------------------------------------------------------------------
# _get_effective_job_management_env — config path exists branch (line 862)
# ---------------------------------------------------------------------------


class TestGetEffectiveJobManagementEnvConfigExists:
    def test_includes_config_path_when_file_exists(self, tmp_path):
        adapter = _build_adapter()
        cfg = tmp_path / "docling-pipelines-config.yaml"
        cfg.write_text("storage: duckdb\n")

        mock_factory = Mock()
        mock_factory.resolve_worker_env.return_value = {}

        with (
            patch.object(adapter, "_resolve_job_management_config_path", return_value=cfg),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.JobManagementFactory.from_default_sources",
                return_value=mock_factory,
            ),
        ):
            result = adapter._get_effective_job_management_env()

        from docpipe.core.constants import EnvironmentVariables

        assert EnvironmentVariables.DOCPIPE_CONFIG_PATH in result


# ---------------------------------------------------------------------------
# _classify_flow_run_result — no-op state branch (all state checks False → return unchanged)
# ---------------------------------------------------------------------------


class TestClassifyFlowRunResultNoOp:
    def test_non_final_non_cancelled_state_is_noop(self):
        """Covers the 647→652 branch: is_cancelled() is False, falls through to return."""
        from prefect.client.schemas.objects import FlowRun as _FlowRun

        adapter = _build_adapter()
        # State that is NOT completed, NOT failed, NOT crashed, NOT cancelled
        state = Mock()
        state.is_completed.return_value = False
        state.is_failed.return_value = False
        state.is_crashed.return_value = False
        state.is_cancelled.return_value = False
        _fid = uuid4()
        result = _FlowRun.model_construct(flow_id=_fid, state=state)
        result.id = _fid
        fr = Mock()
        fr.id = _fid
        failed: list[dict] = []
        count = adapter._classify_flow_run_result(
            batch_num=0, flow_run=fr, result=result, completed_count=7, failed_info=failed, job_run_id="jr"
        )
        # Count unchanged, nothing appended
        assert count == 7
        assert failed == []


# ---------------------------------------------------------------------------
# _build_container_env — all keys pre-populated (covers the False branches 883-898)
# ---------------------------------------------------------------------------


class TestBuildContainerEnvAllKeysPreset:
    def test_does_not_overwrite_any_preset_key(self):
        """All env keys already present → every 'if not in env' branch takes the False path."""
        from docpipe.core.constants import EnvironmentVariables

        adapter = _build_adapter()
        base = {
            EnvironmentVariables.PREFECT_API_URL: "http://a:4200/api",
            EnvironmentVariables.PREFECT_MODE: "server",
            EnvironmentVariables.PYTHONPATH: "/custom/path",
            EnvironmentVariables.OLLAMA_HOST: "http://ollama:11434",
            EnvironmentVariables.PREFECT_LOGGING_EXTRA_LOGGERS: "MY_LOGGER",
        }
        with patch.object(adapter, "_get_effective_job_management_env", return_value={}):
            result = adapter._build_container_env(base_env=base, deployment_path="/app")
        # None of the preset values should be overwritten
        assert result[EnvironmentVariables.PREFECT_API_URL] == "http://a:4200/api"
        assert result[EnvironmentVariables.OLLAMA_HOST] == "http://ollama:11434"
        assert result[EnvironmentVariables.PREFECT_LOGGING_EXTRA_LOGGERS] == "MY_LOGGER"


# ---------------------------------------------------------------------------
# _transfer_batch_inline — binary column with None value (covers 538→536 branch)
# ---------------------------------------------------------------------------


class TestTransferBatchInlineNullBinary:
    def test_null_binary_value_skipped_without_error(self):
        """Covers 538→536: binary column present but value is None → no encoding attempted."""
        adapter = _build_adapter()
        # Binary column with a None value — exercises the False branch of `if value is not None`
        tbl = pa.table({"id": [1, 2], "blob": pa.array([None, b"data"], type=pa.binary())})
        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.get_inline_size_limit",
            return_value=1_000_000,
        ):
            result = adapter._transfer_batch_inline(batch_table=tbl, batch_num=0, job_run_id="jr1")
        # None value stays None, bytes value gets encoded
        rows = result["data"]["data"]
        assert rows[0]["blob"] is None
        import base64

        assert rows[1]["blob"] == base64.b64encode(b"data").decode()


# ---------------------------------------------------------------------------
# _build_container_env — job-management key already in env (covers 898→897 branch)
# ---------------------------------------------------------------------------


class TestBuildContainerEnvJobMgmtKeyConflict:
    def test_does_not_overwrite_job_management_key_already_in_base(self):
        """Covers 898→897: effective_job_management_env key already present in env → skip."""
        from docpipe.core.constants import EnvironmentVariables

        adapter = _build_adapter()
        base = {EnvironmentVariables.PREFECT_API_URL: "http://a:4200/api"}
        # job-management env returns a key that is already in base → the `if env_key not in env` is False
        with patch.object(
            adapter,
            "_get_effective_job_management_env",
            return_value={EnvironmentVariables.PREFECT_API_URL: "http://should-not-overwrite:4200/api"},
        ):
            result = adapter._build_container_env(base_env=base, deployment_path="/app")
        assert result[EnvironmentVariables.PREFECT_API_URL] == "http://a:4200/api"


# ---------------------------------------------------------------------------
# _execute_pipelined_batches_async — covers lines 222-240 and 377-409
# ---------------------------------------------------------------------------


class TestExecutePipelinedBatchesAsync:
    @pytest.mark.asyncio
    async def test_batch_submission_failure_raises_flow_exception(self):
        """
        run_deployment raises immediately → run_single_batch fails → failed_info populated →
        FlowExecutionFailedException raised from line 409.

        The bulk poller task (create_task) is replaced with a no-op coroutine so it
        never enters its infinite while-True loop.
        """
        import asyncio as _asyncio

        adapter = _build_adapter()
        batch = _batch(0)

        async def _noop_poller():
            """Immediately returns so there is no infinite loop."""

        real_create_task = _asyncio.create_task
        call_count = 0

        def fake_create_task(coro, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First create_task call is the bulk poller — replace with noop
                coro.close()  # discard the real coroutine cleanly
                return real_create_task(_noop_poller())
            return real_create_task(coro, **kwargs)

        with (
            patch.object(adapter, "_transfer_batch", return_value={"type": "inline", "data": {}}),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.run_deployment",
                AsyncMock(side_effect=FlowExecutionFailedException("submit failed")),
            ),
            patch.object(adapter, "_cancel_remaining_runs_async", AsyncMock()),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.asyncio.create_task",
                side_effect=fake_create_task,
            ),
        ):
            with pytest.raises(FlowExecutionFailedException):
                await adapter._execute_pipelined_batches_async(
                    batches=[batch], op_flow=[], global_config={}, job_run_id="jr1"
                )
