"""
Unit tests for WorkPoolAdapter.

Tests cover pure-logic paths that do not require a live Prefect server or S3:
- __init__ validation branches (missing work_pool_name, local/S3 storage guards)
- _raise_failure message formatting
- _transfer_batch dispatch routing
- _transfer_batch_inline (happy path, size-limit error, warning threshold)
- _transfer_batch_local (happy path, write error)
- _transfer_batch_s3 (happy path via filesystem mock, write error)
- _resolve_job_management_config_path (env-var override vs. default)
- _build_container_env (default fills, explicit override skipping)
- _build_job_variables (docker, process, and None configs)
- _cleanup_batch_storage (local and S3 branches)
- get_strategy_name
"""

import json
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

# ---------------------------------------------------------------------------
# Prefect stub helpers
#
# WorkPoolAdapter imports from prefect at module level, but prefect is an
# optional heavyweight dependency that may not be installed in the test
# environment, or — when it *is* installed — its real classes must not be
# corrupted for the rest of the pytest session.
#
# Strategy:
#   1. Snapshot the current sys.modules state for every prefect sub-module
#      we need to stub.
#   2. Inject MagicMock stubs only for modules that are NOT already present
#      (environment without prefect).
#   3. For the FlowRun attribute specifically, save the original value and
#      restore it in a session-scoped autouse fixture so the stub never
#      outlives this test module's execution.
# ---------------------------------------------------------------------------

_PREFECT_MODS = [
    "prefect",
    "prefect.client",
    "prefect.client.schemas",
    "prefect.client.schemas.filters",
    "prefect.client.schemas.objects",
    "prefect.deployments",
    "prefect.flow_runs",
    "prefect.futures",
    "prefect.runtime",
    "prefect.runtime.task_run",
    "prefect.settings",
    "prefect.states",
    "prefect.task_runners",
]

# Record which modules were absent before we start, so we can remove them on
# teardown without touching modules that were already loaded.
_mods_injected_by_us: list[str] = []
for _mod in _PREFECT_MODS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
        _mods_injected_by_us.append(_mod)

# Expose the handful of names that prefect_engine.py imports at module level.
_prefect_stub = sys.modules["prefect"]
for _attr in ("flow", "task", "get_client"):
    if not hasattr(_prefect_stub, _attr):
        setattr(_prefect_stub, _attr, MagicMock())

_schemas_objects_mod: ModuleType = sys.modules["prefect.client.schemas.objects"]
_FlowRunClass = type("FlowRun", (), {})


@pytest.fixture(scope="module", autouse=True)
def _patch_prefect_flowrun():
    """
    Swap FlowRun with a minimal stub for the duration of this test module only,
    then restore the original so other test files are not affected.

    scope="module" ensures the swap is in place for all tests in this file and
    is reversed before any other test module runs.
    """
    original = getattr(_schemas_objects_mod, "FlowRun", None)
    _schemas_objects_mod.FlowRun = _FlowRunClass  # type: ignore[attr-defined]
    yield
    if original is not None:
        _schemas_objects_mod.FlowRun = original  # type: ignore[attr-defined]
    else:
        try:
            delattr(_schemas_objects_mod, "FlowRun")
        except AttributeError:
            pass
    for _mod in _mods_injected_by_us:
        sys.modules.pop(_mod, None)


# ---------------------------------------------------------------------------
# Now it is safe to import from docpipe.
# ---------------------------------------------------------------------------
from docpipe.core.orchestration.prefect.adapters.work_pool_adapter import WorkPoolAdapter  # noqa: E402
from docpipe.core.orchestration.prefect.domain.models import (  # noqa: E402
    BatchStorageType,
    BatchStrategyConstants,
)
from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException  # noqa: E402

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_adapter(*, extra_config: dict | None = None):
    """
    Build a WorkPoolAdapter with Prefect connectivity side-effects patched out.
    """
    base_config: dict = {
        "work_pool_name": "test-pool",
        "type": "process",
    }
    if extra_config:
        base_config.update(extra_config)

    mock_engine = MagicMock()
    mock_engine.logger = MagicMock()

    with (
        patch.object(WorkPoolAdapter, "_validate_prefect_connection", return_value=None),
        patch.object(WorkPoolAdapter, "_ensure_deployment_exists", return_value=None),
    ):
        return WorkPoolAdapter(
            work_pool_config=base_config,
            prefect_engine=mock_engine,
            batch_manager=MagicMock(),
        )


def _small_table() -> pa.Table:
    return pa.table(
        {
            "id": ["doc1", "doc2"],
            "content": ["hello world", "foo bar"],
            "name": ["a.txt", "b.txt"],
        }
    )


# ---------------------------------------------------------------------------
# TestWorkPoolAdapterInit
# ---------------------------------------------------------------------------


class TestWorkPoolAdapterInit:
    """Validation logic in __init__."""

    def test_missing_work_pool_name_raises(self):
        with (
            patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
            patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
            pytest.raises(ValueError, match="work_pool_name is required"),
        ):
            WorkPoolAdapter(
                work_pool_config={},
                prefect_engine=MagicMock(),
                batch_manager=MagicMock(),
            )

    def test_local_storage_without_path_raises(self):
        with (
            patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
            patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
            pytest.raises(ValueError, match=r"batch_storage\.path is required"),
        ):
            WorkPoolAdapter(
                work_pool_config={
                    "work_pool_name": "pool",
                    "batch_storage": {"type": "local"},
                },
                prefect_engine=MagicMock(),
                batch_manager=MagicMock(),
            )

    def test_s3_storage_without_bucket_raises(self):
        with (
            patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
            patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
            pytest.raises(ValueError, match=r"batch_storage\.bucket is required"),
        ):
            WorkPoolAdapter(
                work_pool_config={
                    "work_pool_name": "pool",
                    "batch_storage": {
                        "type": "s3",
                        "access_key_id": "key",
                        "secret_access_key": "secret",  # pragma: allowlist secret
                    },
                },
                prefect_engine=MagicMock(),
                batch_manager=MagicMock(),
            )

    def test_s3_storage_without_credentials_raises(self):
        with (
            patch.object(WorkPoolAdapter, "_validate_prefect_connection"),
            patch.object(WorkPoolAdapter, "_ensure_deployment_exists"),
            pytest.raises(ValueError, match="S3 credentials are required"),
        ):
            WorkPoolAdapter(
                work_pool_config={
                    "work_pool_name": "pool",
                    "batch_storage": {"type": "s3", "bucket": "my-bucket"},
                },
                prefect_engine=MagicMock(),
                batch_manager=MagicMock(),
            )

    def test_valid_inline_config_initialises_defaults(self):
        adapter = _make_adapter()
        assert adapter.work_pool_name == "test-pool"
        assert adapter.batch_storage_type == BatchStorageType.INLINE
        assert adapter.deployment_name == BatchStrategyConstants.DEFAULT_DEPLOYMENT_NAME

    def test_get_strategy_name(self):
        adapter = _make_adapter()
        assert adapter.get_strategy_name() == "work-pool-process"


# ---------------------------------------------------------------------------
# TestRaiseFailure
# ---------------------------------------------------------------------------


class TestRaiseFailure:
    """_raise_failure must include batch numbers and run IDs in the message."""

    def test_raises_with_details(self):
        failed = [
            {"batch_num": 1, "run_id": "abc-123", "message": "timeout"},
            {"batch_num": 2, "run_id": "def-456", "message": "crash"},
        ]
        with pytest.raises(FlowExecutionFailedException, match="Batch 1") as exc_info:
            WorkPoolAdapter._raise_failure(failed_info=failed, completed_count=0, total_count=3)

        error_text = str(exc_info.value)
        assert "abc-123" in error_text
        assert "timeout" in error_text
        assert "Batch 2" in error_text
        assert "def-456" in error_text
        assert "Failed: 2" in error_text
        assert "Completed: 0" in error_text
        assert "Total: 3" in error_text


# ---------------------------------------------------------------------------
# TestTransferBatchDispatch
# ---------------------------------------------------------------------------


class TestTransferBatchDispatch:
    """_transfer_batch should route to the correct storage-type handler."""

    @pytest.mark.parametrize(
        ("storage_type", "expected_method"),
        [
            (BatchStorageType.S3, "_transfer_batch_s3"),
            (BatchStorageType.LOCAL, "_transfer_batch_local"),
            (BatchStorageType.INLINE, "_transfer_batch_inline"),
        ],
    )
    def test_dispatch_routing(self, storage_type, expected_method):
        adapter = _make_adapter()
        adapter.batch_storage_type = storage_type

        with patch.object(adapter, expected_method, return_value={"type": storage_type.value}) as mock_method:
            result = adapter._transfer_batch(batch_table=_small_table(), batch_num=1, job_run_id="jr-1")

        mock_method.assert_called_once()
        assert result == {"type": storage_type.value}


# ---------------------------------------------------------------------------
# TestTransferBatchInline
# ---------------------------------------------------------------------------


class TestTransferBatchInline:
    """_transfer_batch_inline serialisation and size-limit paths."""

    def test_returns_inline_descriptor(self):
        adapter = _make_adapter()
        table = _small_table()

        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.get_inline_size_limit",
            return_value=10 * 1024 * 1024,
        ):
            result = adapter._transfer_batch_inline(batch_table=table, batch_num=0, job_run_id="jr-1")

        assert result["type"] == BatchStorageType.INLINE.value
        assert "data" in result
        payload = result["data"]
        assert payload["row_count"] == 2
        assert set(payload["columns"]) == {"id", "content", "name"}

    def test_raises_when_exceeds_size_limit(self):
        adapter = _make_adapter()

        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.get_inline_size_limit",
                return_value=1,
            ),
            pytest.raises(FlowExecutionFailedException, match="exceeding Prefect"),
        ):
            adapter._transfer_batch_inline(batch_table=_small_table(), batch_num=0, job_run_id="jr-1")

    def test_warns_when_approaching_size_limit(self):
        adapter = _make_adapter()
        table = _small_table()

        # Compute the actual serialised size so we can pick a limit that is
        # just above it (triggering the 80% warning) but still below 100%.
        actual_size = len(
            json.dumps(
                {
                    "columns": table.column_names,
                    "data": table.to_pylist(),
                    "schema": {col: str(table.schema.field(col).type) for col in table.column_names},
                    "row_count": len(table),
                    "binary_columns": [],
                }
            ).encode()
        )
        tight_limit = int(actual_size / 0.9) + 1

        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.get_inline_size_limit",
            return_value=tight_limit,
        ):
            adapter._transfer_batch_inline(batch_table=table, batch_num=0, job_run_id="jr-1")

        adapter.prefect_engine.logger.warning.assert_called()

    def test_base64_encodes_binary_columns(self):
        adapter = _make_adapter()
        binary_table = pa.table({"id": ["doc1"], "content": [b"\x00\x01\x02"]})

        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.BatchStrategyConstants.get_inline_size_limit",
            return_value=10 * 1024 * 1024,
        ):
            result = adapter._transfer_batch_inline(batch_table=binary_table, batch_num=0, job_run_id="jr-1")

        assert "content" in result["data"]["binary_columns"]
        assert isinstance(result["data"]["data"][0]["content"], str)


# ---------------------------------------------------------------------------
# TestTransferBatchLocal
# ---------------------------------------------------------------------------


class TestTransferBatchLocal:
    """_transfer_batch_local file-write paths."""

    def test_writes_parquet_and_returns_descriptor(self, tmp_path):
        adapter = _make_adapter()
        adapter.batch_storage_path = str(tmp_path)

        with (
            patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.pq.write_table"),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.replace_memmap_paths_combined",
                side_effect=lambda table: table,
            ),
        ):
            result = adapter._transfer_batch_local(batch_table=_small_table(), batch_num=3, job_run_id="jr-99")

        assert result["type"] == BatchStorageType.LOCAL.value
        assert "jr-99" in result["ref"]
        assert "batch-3.parquet" in result["ref"]

    def test_raises_on_write_failure(self, tmp_path):
        adapter = _make_adapter()
        adapter.batch_storage_path = str(tmp_path)

        with (
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.pq.write_table",
                side_effect=OSError("disk full"),
            ),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.replace_memmap_paths_combined",
                side_effect=lambda table: table,
            ),
            pytest.raises(FlowExecutionFailedException, match="disk full"),
        ):
            adapter._transfer_batch_local(batch_table=_small_table(), batch_num=0, job_run_id="jr-1")


# ---------------------------------------------------------------------------
# TestTransferBatchS3
# ---------------------------------------------------------------------------


class TestTransferBatchS3:
    """_transfer_batch_s3 write paths via mocked S3FileSystem."""

    def test_returns_s3_descriptor(self):
        adapter = _make_adapter()
        adapter.batch_storage_bucket = "my-bucket"
        adapter.batch_storage_prefix = "tmp/"
        adapter.s3_access_key = "ak"
        adapter.s3_secret_key = "sk"  # pragma: allowlist secret
        adapter.s3_endpoint_url = None
        adapter.s3_region = None

        with (
            patch.object(adapter, "_create_s3_filesystem", return_value=MagicMock()),
            patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.pq.write_table"),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.replace_memmap_paths_combined",
                side_effect=lambda table: table,
            ),
        ):
            result = adapter._transfer_batch_s3(batch_table=_small_table(), batch_num=7, job_run_id="jr-7")

        assert result["type"] == BatchStorageType.S3.value
        assert result["bucket"] == "my-bucket"
        assert "batch-7.parquet" in result["ref"]
        assert result["access_key"] == "ak"

    def test_raises_on_s3_write_failure(self):
        adapter = _make_adapter()
        adapter.batch_storage_bucket = "my-bucket"
        adapter.batch_storage_prefix = "tmp/"
        adapter.s3_access_key = "ak"
        adapter.s3_secret_key = "sk"  # pragma: allowlist secret
        adapter.s3_endpoint_url = None

        with (
            patch.object(adapter, "_create_s3_filesystem", return_value=MagicMock()),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.pq.write_table",
                side_effect=RuntimeError("S3 unavailable"),
            ),
            patch(
                "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.replace_memmap_paths_combined",
                side_effect=lambda table: table,
            ),
            pytest.raises(FlowExecutionFailedException, match="S3 unavailable"),
        ):
            adapter._transfer_batch_s3(batch_table=_small_table(), batch_num=0, job_run_id="jr-1")


# ---------------------------------------------------------------------------
# TestResolveJobManagementConfigPath
# ---------------------------------------------------------------------------


class TestResolveJobManagementConfigPath:
    """_resolve_job_management_config_path env-var override and default fallback."""

    def test_returns_env_var_path_when_set(self, tmp_path):
        config_file = tmp_path / "custom-config.yaml"
        config_file.touch()

        with patch.dict(os.environ, {"DOCPIPE_CONFIG_PATH": str(config_file)}):
            result = WorkPoolAdapter._resolve_job_management_config_path()

        assert result == config_file.resolve()

    def test_returns_default_path_when_env_not_set(self):
        env = os.environ.copy()
        env.pop("DOCPIPE_CONFIG_PATH", None)

        with patch.dict(os.environ, env, clear=True):
            result = WorkPoolAdapter._resolve_job_management_config_path()

        assert result.name == "docling-pipelines-config.yaml"
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# TestBuildContainerEnv
# ---------------------------------------------------------------------------


class TestBuildContainerEnv:
    """_build_container_env fills defaults only when keys are absent."""

    def test_fills_prefect_api_url_default(self):
        adapter = _make_adapter()
        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.JobManagementFactory"
        ) as mock_factory:
            mock_factory.from_default_sources.return_value.resolve_worker_env.return_value = {}
            env = adapter._build_container_env(base_env={}, deployment_path=None)

        assert "PREFECT_API_URL" in env

    def test_does_not_overwrite_existing_prefect_api_url(self):
        adapter = _make_adapter()
        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.JobManagementFactory"
        ) as mock_factory:
            mock_factory.from_default_sources.return_value.resolve_worker_env.return_value = {}
            env = adapter._build_container_env(
                base_env={"PREFECT_API_URL": "http://custom:4200/api"}, deployment_path=None
            )

        assert env["PREFECT_API_URL"] == "http://custom:4200/api"

    def test_fills_prefect_mode_default(self):
        adapter = _make_adapter()
        with patch(
            "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.JobManagementFactory"
        ) as mock_factory:
            mock_factory.from_default_sources.return_value.resolve_worker_env.return_value = {}
            env = adapter._build_container_env(base_env={}, deployment_path=None)

        assert env.get("PREFECT_MODE") == "server"


# ---------------------------------------------------------------------------
# TestBuildJobVariables
# ---------------------------------------------------------------------------


class TestBuildJobVariables:
    """_build_job_variables returns correct structure per work pool config type."""

    def test_returns_none_for_unknown_config(self):
        adapter = _make_adapter()
        adapter.work_pool_runtime_config = object()
        assert adapter._build_job_variables() is None

    def test_process_config_returns_env_dict(self):
        from docpipe.core.orchestration.prefect.config.work_pool_config import ProcessWorkPoolConfig

        adapter = _make_adapter()
        adapter.work_pool_runtime_config = ProcessWorkPoolConfig(env={"MY_VAR": "value"})

        with patch.object(adapter, "_build_container_env", return_value={"MY_VAR": "value"}):
            result = adapter._build_job_variables()

        assert result is not None
        assert "env" in result

    def test_docker_config_returns_image_and_env(self):
        from docpipe.core.orchestration.prefect.config.work_pool_config import DockerWorkPoolConfig

        adapter = _make_adapter()
        adapter.work_pool_runtime_config = DockerWorkPoolConfig(image="myimage:1.0")

        with patch.object(adapter, "_build_container_env", return_value={}):
            result = adapter._build_job_variables()

        assert result is not None
        assert result["image"] == "myimage:1.0"
        assert "env" in result


# ---------------------------------------------------------------------------
# TestCleanupBatchStorage
# ---------------------------------------------------------------------------


class TestCleanupBatchStorage:
    """_cleanup_batch_storage covers local (delete), S3 (log only), and inline (no-op)."""

    def test_local_cleanup_removes_directory(self, tmp_path):
        adapter = _make_adapter()
        adapter.batch_storage_type = BatchStorageType.LOCAL
        adapter.batch_storage_path = str(tmp_path)

        batch_dir = tmp_path / "jr-cleanup"
        batch_dir.mkdir()
        (batch_dir / "batch-0.parquet").touch()

        adapter._cleanup_batch_storage(job_run_id="jr-cleanup")

        assert not batch_dir.exists()
        adapter.prefect_engine.logger.info.assert_called()

    def test_local_cleanup_handles_missing_dir_gracefully(self, tmp_path):
        adapter = _make_adapter()
        adapter.batch_storage_type = BatchStorageType.LOCAL
        adapter.batch_storage_path = str(tmp_path)

        # Must not raise when the per-job directory doesn't exist.
        adapter._cleanup_batch_storage(job_run_id="nonexistent-dir")

    def test_s3_cleanup_only_logs(self):
        adapter = _make_adapter()
        adapter.batch_storage_type = BatchStorageType.S3
        adapter.batch_storage_bucket = "bucket"
        adapter.batch_storage_prefix = "prefix/"

        adapter._cleanup_batch_storage(job_run_id="jr-s3")

        adapter.prefect_engine.logger.info.assert_called()

    def test_inline_cleanup_does_nothing(self):
        adapter = _make_adapter()
        adapter.batch_storage_type = BatchStorageType.INLINE

        adapter.prefect_engine.logger.reset_mock()
        adapter._cleanup_batch_storage(job_run_id="jr-inline")

        adapter.prefect_engine.logger.info.assert_not_called()
        adapter.prefect_engine.logger.warning.assert_not_called()
