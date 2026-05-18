"""
WorkPoolAdapter - Distributed batch execution via Prefect work pools.

This adapter implements distributed execution by submitting batches to
Prefect deployments that are executed by remote workers.

Uses Prefect's native high-level APIs:
- run_deployment() for non-blocking flow run submission
- wait_for_flow_run() for efficient state monitoring (event-based, not polling)
- get_client(sync_client=True) for synchronous Prefect API calls

Supports configurable batch data transfer:
- S3: For cross-machine distributed execution (production)
- Local filesystem: For Docker Compose / single-machine setups
- Inline (parameters): For small batches (<512KB) without shared storage
"""

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from prefect import get_client
from prefect.client.schemas.objects import FlowRun
from prefect.deployments import run_deployment
from prefect.flow_runs import wait_for_flow_run
from prefect.states import Cancelled

from datasift.core.constants import EnvironmentVariables
from datasift.core.job_management.adapters.config.job_management_factory import JobManagementFactory
from datasift.core.orchestration.batch_manager import BatchInfo
from datasift.core.orchestration.prefect.config.work_pool_config import (
    DockerWorkPoolConfig,
    ECSWorkPoolConfig,
    KubernetesWorkPoolConfig,
    ProcessWorkPoolConfig,
    create_work_pool_config,
)
from datasift.core.orchestration.prefect.domain.models import (
    BatchStorageType,
    BatchStrategyConstants,
    WorkPoolType,
)
from datasift.core.orchestration.prefect.ports.batch_execution_port import BatchExecutionPort
from datasift.exceptions.datasift_exceptions import FlowExecutionFailedException
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger()


class WorkPoolAdapter(BatchExecutionPort):
    """
    Adapter: Distributed batch execution via Prefect work pools.

    This strategy submits batches to Prefect deployments which are executed
    by workers polling from work pools. Each batch runs on a potentially
    different worker machine.

    Architecture:
    - User's machine: Submits flow runs to Prefect Server
    - Prefect Server: Queues flow runs in work pool
    - Workers: Poll work pool, execute flow runs, report results

    Batch Data Transfer:
    - S3: Write to S3 bucket, pass URI as parameter (cross-machine)
    - Local: Write to shared filesystem, pass path as parameter (same machine)
    - Inline: Serialize to JSON in parameters (small data only, <512KB)

    Characteristics:
    - Non-blocking submission via run_deployment(timeout=0)
    - Efficient monitoring via wait_for_flow_run() (event-based in Prefect v3)
    - Fail-fast: First failure triggers cancellation of remaining batches
    - Network-dependent: Requires Prefect Server accessible

    Use Cases:
    - Production deployments with multiple workers
    - Large-scale data processing
    - When horizontal scalability is needed
    - Distributed team environments
    """

    def __init__(self, *, work_pool_config: dict[str, Any], prefect_engine, batch_manager):
        """
        Initialize work pool adapter.

        Args:
            work_pool_config: Configuration for work pool
                {
                    "type": "process|docker|kubernetes|ecs",
                    "work_pool_name": "datasift-pool",
                    "deployment_name": "datasift-batch-subflow",
                    "batch_storage": {
                        "type": "s3|local|inline",
                        "bucket": "my-bucket",          # S3 only
                        "prefix": "tmp/batches/",       # S3 only
                        "path": "/data/batches"          # local only
                    }
                }
            prefect_engine: PrefectEngine instance (for accessing flow building)
            batch_manager: BatchManager instance (for batch operations)

        Raises:
            ValueError: If required config parameters are missing
        """
        self.work_pool_config = work_pool_config
        self.prefect_engine = prefect_engine
        self.batch_manager = batch_manager

        # Extract configuration using constants
        self.work_pool_type = work_pool_config.get(BatchStrategyConstants.CONFIG_KEY_TYPE, WorkPoolType.PROCESS.value)
        self.work_pool_name = work_pool_config.get(BatchStrategyConstants.CONFIG_KEY_WORK_POOL_NAME)
        self.deployment_name = work_pool_config.get(
            BatchStrategyConstants.CONFIG_KEY_DEPLOYMENT_NAME, BatchStrategyConstants.DEFAULT_DEPLOYMENT_NAME
        )
        self.work_pool_runtime_config = create_work_pool_config(
            work_pool_type=self.work_pool_type,
            config_dict=work_pool_config,
        )

        # Batch storage configuration
        batch_storage_config = work_pool_config.get(BatchStrategyConstants.CONFIG_KEY_BATCH_STORAGE, {})
        self.batch_storage_type = BatchStorageType(
            batch_storage_config.get(
                BatchStrategyConstants.CONFIG_KEY_BATCH_STORAGE_TYPE, BatchStorageType.INLINE.value
            )
        )
        self.batch_storage_path = batch_storage_config.get(BatchStrategyConstants.CONFIG_KEY_BATCH_STORAGE_PATH)
        self.batch_storage_bucket = batch_storage_config.get(BatchStrategyConstants.CONFIG_KEY_BATCH_STORAGE_BUCKET)
        self.batch_storage_prefix = batch_storage_config.get(
            BatchStrategyConstants.CONFIG_KEY_BATCH_STORAGE_PREFIX, "tmp/batches/"
        )

        # S3 credentials (required when batch_storage.type is 's3')
        # Support both AWS standard names and shorter aliases
        self.s3_access_key = batch_storage_config.get("access_key_id") or batch_storage_config.get("access_key")
        self.s3_secret_key = batch_storage_config.get("secret_access_key") or batch_storage_config.get("secret_key")
        self.s3_endpoint_url = batch_storage_config.get("endpoint_url")
        self.s3_region = batch_storage_config.get("region")

        # Validate required parameters
        if not self.work_pool_name:
            raise ValueError(
                f"{BatchStrategyConstants.CONFIG_KEY_WORK_POOL_NAME} is required for WorkPool strategy. "
                f"Set in global_config.prefect.batch_execution.{BatchStrategyConstants.CONFIG_KEY_WORK_POOL_NAME}"
            )

        # Validate batch storage-specific requirements
        if self.batch_storage_type == BatchStorageType.LOCAL and not self.batch_storage_path:
            raise ValueError(
                "batch_storage.path is required when batch_storage.type is 'local'. "
                "Set the shared filesystem path accessible by both submitter and workers."
            )

        if self.batch_storage_type == BatchStorageType.S3:
            if not self.batch_storage_bucket:
                raise ValueError(
                    "batch_storage.bucket is required when batch_storage.type is 's3'. "
                    "Set the S3 bucket name accessible by both submitter and workers."
                )
            if not self.s3_access_key or not self.s3_secret_key:
                raise ValueError(
                    "S3 credentials are required when batch_storage.type is 's3'. "
                    "Provide either (access_key_id, secret_access_key) or (access_key, secret_key). "
                    "These credentials must have read/write access to the specified bucket."
                )

        # Validate Prefect Server connectivity
        self._validate_prefect_connection()

        # Ensure deployment exists in Prefect Server
        # This must happen after validation so we know the server is reachable
        self._ensure_deployment_exists()

    def execute_batches(
        self, *, batches: list[BatchInfo], op_flow: list[dict], global_config: dict, job_run_id: str
    ) -> None:
        """
        Execute batches using distributed work pool with semaphore-controlled concurrency.

        Process:
        1. Acquire semaphore slot (respecting max_concurrent_batches)
        2. Transfer batch data to storage (S3/local/inline)
        3. Submit batch as a flow run via run_deployment()
        4. Wait for completion via wait_for_flow_run()
        5. Release slot and repeat for remaining batches
        """
        self.prefect_engine.logger.info(
            f"Executing {len(batches)} batches using WorkPool strategy "
            f"(pool={self.work_pool_name}, type={self.work_pool_type}, "
            f"storage={self.batch_storage_type.value})",
            extra={"job_run_id": job_run_id},
        )

        # Run the pipelined execution in the event loop
        asyncio.run(
            self._execute_pipelined_batches_async(
                batches=batches,
                op_flow=op_flow,
                global_config=global_config,
                job_run_id=job_run_id,
            )
        )

        # Cleanup batch storage (best-effort)
        self._cleanup_batch_storage(job_run_id=job_run_id)

        self.prefect_engine.logger.info("All batches completed successfully", extra={"job_run_id": job_run_id})

    async def _execute_pipelined_batches_async(
        self, *, batches: list[BatchInfo], op_flow: list[dict], global_config: dict, job_run_id: str
    ) -> None:
        """
        Async implementation of pipelined batch execution.
        """
        # Get concurrency limit from config or fallback to a safe default
        from datasift.core.constants.constants import DatasiftConstants

        max_concurrent = global_config.get(DatasiftConstants.MAX_CONCURRENT_BATCHES, 10)
        semaphore = asyncio.Semaphore(max_concurrent)

        self.prefect_engine.logger.info(
            f"Using submission semaphore with {max_concurrent} slots", extra={"job_run_id": job_run_id}
        )

        completed_count = 0
        failed_info = []
        submitted_runs: list[FlowRun] = []

        async def run_single_batch(batch_info: BatchInfo):
            nonlocal completed_count
            async with semaphore:
                try:
                    # 1. Transfer batch data (happens within semaphore to limit I/O spikes)
                    batch_transfer = self._transfer_batch(
                        batch_table=batch_info.table, batch_num=batch_info.batch_num, job_run_id=job_run_id
                    )

                    # 2. Submit flow run
                    deployment_full_name = f"{BatchStrategyConstants.BATCH_SUBFLOW_NAME}/{self.deployment_name}"

                    # run_deployment is non-blocking with timeout=0
                    flow_run_result = await run_deployment(
                        name=deployment_full_name,
                        parameters={
                            "batch_id": batch_info.batch_id,
                            "batch_num": batch_info.batch_num,
                            "batch_transfer": batch_transfer,
                            "op_flow": op_flow,
                            "global_config": global_config,
                            "job_run_id": job_run_id,
                        },
                        timeout=0,
                        as_subflow=False,
                    )

                    if not flow_run_result or not isinstance(flow_run_result, FlowRun):
                        raise FlowExecutionFailedException(f"Failed to submit batch {batch_info.batch_num}")

                    # Type-safe: flow_run_result is now confirmed to be FlowRun
                    submitted_runs.append(flow_run_result)
                    current_flow_run_id = flow_run_result.id  # type: ignore[attr-defined]
                    self.prefect_engine.logger.info(
                        f"Batch {batch_info.batch_num} submitted: flow_run_id={current_flow_run_id}",
                        extra={"job_run_id": job_run_id},
                    )

                    # 3. Wait for completion (with safety loop for premature returns)
                    final_flow_run: FlowRun | None = None
                    while True:
                        wait_result = await wait_for_flow_run(
                            flow_run_id=current_flow_run_id,
                            timeout=10800,  # 3 hours timeout per batch
                            log_states=True,
                        )

                        if not wait_result or not isinstance(wait_result, FlowRun):
                            await asyncio.sleep(2)
                            continue

                        # Type-safe: wait_result is confirmed to be FlowRun
                        state = wait_result.state  # type: ignore[attr-defined]
                        if state:
                            # Primary check
                            if state.is_final():
                                final_flow_run = wait_result
                                break
                            # Fallback check for manual state transitions
                            state_name = str(state.name).lower()
                            if state_name in ["completed", "failed", "cancelled", "crashed"]:
                                self.prefect_engine.logger.warning(
                                    f"Batch {batch_info.batch_num}: State '{state_name}' detected via fallback. Breaking wait loop.",
                                    extra={"job_run_id": job_run_id},
                                )
                                final_flow_run = wait_result
                                break

                        # If not final, small sleep and re-check
                        await asyncio.sleep(2)

                    # 4. Process result
                    is_completed = False
                    if final_flow_run:
                        state = final_flow_run.state

                        if state:
                            # Primary: Official Prefect 3.x completion check
                            if state.is_completed():
                                is_completed = True
                            # Secondary: String-based name check (robust against enum mismatches)
                            elif str(state.name).lower() == "completed":
                                is_completed = True

                        if is_completed:
                            completed_count += 1
                            self.prefect_engine.logger.info(
                                f"Batch {batch_info.batch_num} completed successfully", extra={"job_run_id": job_run_id}
                            )
                        else:
                            # Log full state diagnostics for debugging
                            state_type_str = getattr(getattr(state, "type", None), "value", "N/A") if state else "N/A"
                            state_name_str = getattr(state, "name", "N/A") if state else "N/A"
                            state_msg = state.message if state else "Unknown state"
                            self.prefect_engine.logger.error(
                                f"Batch {batch_info.batch_num} NOT completed — "
                                f"state_type={state_type_str}, state_name={state_name_str}, "
                                f"message={state_msg}",
                                extra={"job_run_id": job_run_id},
                            )
                            failed_info.append(
                                {
                                    "batch_num": batch_info.batch_num,
                                    "run_id": str(current_flow_run_id),
                                    "message": f"state_type={state_type_str}, name={state_name_str}, msg={state_msg}",
                                }
                            )

                except Exception as e:
                    failed_info.append({"batch_num": batch_info.batch_num, "run_id": "N/A", "message": str(e)})
                    self.prefect_engine.logger.error(
                        f"Exception in batch {batch_info.batch_num}: {e}",
                        extra={"job_run_id": job_run_id},
                        exc_info=True,
                    )

        # Create all tasks as explicit asyncio.Task objects so we can cancel them
        running_tasks = [asyncio.create_task(run_single_batch(b)) for b in batches]

        try:
            # Monitor tasks as they complete
            for coro in asyncio.as_completed(running_tasks):
                await coro
                if failed_info:
                    # First failure detected, break the monitoring loop
                    break
        finally:
            # CRITICAL: If we break due to failure (or an exception occurs),
            # we must cancel ALL background tasks that haven't finished yet.
            # This prevents "ghost submissions" of remaining batches.
            still_running = [t for t in running_tasks if not t.done()]
            if still_running:
                self.prefect_engine.logger.warning(
                    f"Cancelling {len(still_running)} background submission tasks", extra={"job_run_id": job_run_id}
                )
                for t in still_running:
                    t.cancel()

                # Wait for cancellation to settle
                await asyncio.gather(*still_running, return_exceptions=True)

        # If any failures occurred, cancel the remote Prefect flow runs and raise
        if failed_info:
            await self._cancel_remaining_runs_async(flow_runs=submitted_runs, job_run_id=job_run_id)
            self._raise_failure(failed_info=failed_info, completed_count=completed_count, total_count=len(batches))

    # ─── Batch Data Transfer ────────────────────────────────────────────

    def _transfer_batch(self, *, batch_table: pa.Table, batch_num: int, job_run_id: str) -> dict[str, Any]:
        """
        Transfer batch data to storage for worker access.

        Returns a transfer descriptor dict that tells the worker how and
        where to load the batch data.

        Args:
            batch_table: PyArrow table to transfer
            batch_num: Batch number for identification
            job_run_id: Job run ID for path namespacing

        Returns:
            Dict describing the transfer:
            - {"type": "s3", "ref": "s3://bucket/path/batch-0.parquet"}
            - {"type": "local", "ref": "/data/batches/job-123/batch-0.parquet"}
            - {"type": "inline", "data": {...}}
        """
        if self.batch_storage_type == BatchStorageType.S3:
            return self._transfer_batch_s3(batch_table=batch_table, batch_num=batch_num, job_run_id=job_run_id)
        elif self.batch_storage_type == BatchStorageType.LOCAL:
            return self._transfer_batch_local(batch_table=batch_table, batch_num=batch_num, job_run_id=job_run_id)
        else:
            return self._transfer_batch_inline(batch_table=batch_table, batch_num=batch_num, job_run_id=job_run_id)

    def _create_s3_filesystem(self):
        """
        Create a PyArrow S3FileSystem with explicit credentials.

        Uses the same credential pattern as datasift's S3SourceAdapter
        (access_key, secret_key, endpoint_url, region).

        Returns:
            pyarrow.fs.S3FileSystem configured with credentials
        """
        from pyarrow.fs import S3FileSystem

        fs_kwargs = {
            "access_key": self.s3_access_key,
            "secret_key": self.s3_secret_key,
        }

        if self.s3_region:
            fs_kwargs["region"] = self.s3_region

        if self.s3_endpoint_url:
            # For S3-compatible storage (MinIO, IBM COS, etc.)
            fs_kwargs["endpoint_override"] = self.s3_endpoint_url

        return S3FileSystem(**fs_kwargs)

    def _transfer_batch_s3(self, *, batch_table: pa.Table, batch_num: int, job_run_id: str) -> dict[str, Any]:
        """Write batch to S3 using PyArrow S3FileSystem with explicit credentials."""
        s3_key = f"{self.batch_storage_prefix}{job_run_id}/batch-{batch_num}.parquet"
        s3_uri = f"s3://{self.batch_storage_bucket}/{s3_key}"

        try:
            s3_fs = self._create_s3_filesystem()

            # Write using the authenticated filesystem
            pq.write_table(batch_table, f"{self.batch_storage_bucket}/{s3_key}", filesystem=s3_fs)

            self.prefect_engine.logger.info(
                f"Batch {batch_num}: written to S3 ({len(batch_table)} rows) → {s3_uri}",
                extra={"job_run_id": job_run_id},
            )

            # Return credentials in transfer descriptor so workers can read
            return {
                "type": BatchStorageType.S3.value,
                "ref": s3_uri,
                "bucket": self.batch_storage_bucket,
                "key": s3_key,
                "access_key": self.s3_access_key,
                "secret_key": self.s3_secret_key,
                "endpoint_url": self.s3_endpoint_url,
                "region": self.s3_region,
            }
        except Exception as e:
            raise FlowExecutionFailedException(f"Failed to write batch {batch_num} to S3 ({s3_uri}): {e}") from e

    def _transfer_batch_local(self, *, batch_table: pa.Table, batch_num: int, job_run_id: str) -> dict[str, Any]:
        """Write batch to local shared filesystem and return path."""
        batch_dir = os.path.join(self.batch_storage_path, job_run_id)
        os.makedirs(batch_dir, exist_ok=True)

        local_path = os.path.join(batch_dir, f"batch-{batch_num}.parquet")

        try:
            pq.write_table(batch_table, local_path)

            self.prefect_engine.logger.info(
                f"Batch {batch_num}: written to local ({len(batch_table)} rows) → {local_path}",
                extra={"job_run_id": job_run_id},
            )

            return {"type": BatchStorageType.LOCAL.value, "ref": local_path}
        except Exception as e:
            raise FlowExecutionFailedException(
                f"Failed to write batch {batch_num} to local path ({local_path}): {e}"
            ) from e

    def _transfer_batch_inline(self, *, batch_table: pa.Table, batch_num: int, job_run_id: str) -> dict[str, Any]:
        """Serialize batch to JSON dict for passing as Prefect parameter."""
        # Detect binary columns (binary or large_binary types)
        binary_columns = [
            col_name
            for col_name in batch_table.column_names
            if pa.types.is_binary(batch_table.schema.field(col_name).type)
            or pa.types.is_large_binary(batch_table.schema.field(col_name).type)
        ]

        # Convert table to list of dicts
        data = batch_table.to_pylist()

        # Base64-encode binary columns for JSON serialization
        if binary_columns:
            for row in data:
                for col_name in binary_columns:
                    value = row.get(col_name)
                    if value is not None and isinstance(value, bytes):
                        # Encode bytes to base64 string
                        row[col_name] = base64.b64encode(value).decode("utf-8")

        batch_dict = {
            "columns": batch_table.column_names,
            "data": data,
            "schema": {col: str(batch_table.schema.field(col).type) for col in batch_table.column_names},
            "row_count": len(batch_table),
            "binary_columns": binary_columns,
        }

        # Check size and warn/error if too large
        size_bytes = len(json.dumps(batch_dict).encode("utf-8"))
        size_limit = BatchStrategyConstants.get_inline_size_limit()
        warning_threshold = int(size_limit * BatchStrategyConstants.INLINE_SIZE_WARNING_THRESHOLD)

        self.prefect_engine.logger.info(
            f"Batch {batch_num}: serialized inline ({len(batch_table)} rows, {size_bytes:,} bytes)",
            extra={"job_run_id": job_run_id, "size_bytes": size_bytes},
        )

        if size_bytes > size_limit:
            raise FlowExecutionFailedException(
                f"Batch {batch_num} is {size_bytes:,} bytes, exceeding Prefect's "
                f"parameter limit (PREFECT_SERVER_API_MAX_PARAMETER_SIZE={size_limit:,} bytes). "
                f"Options:\n"
                f"1. Configure batch_storage with type 's3' or 'local' for larger batches:\n"
                f'   "batch_storage": {{"type": "s3", "bucket": "my-bucket"}}\n'
                f"2. Increase the limit by setting PREFECT_SERVER_API_MAX_PARAMETER_SIZE environment variable on Prefect Server:\n"
                f"   export PREFECT_SERVER_API_MAX_PARAMETER_SIZE=2097152  # 2MB\n"
                f"3. Disable the limit entirely (not recommended):\n"
                f"   export PREFECT_SERVER_API_MAX_PARAMETER_SIZE=0"
            )
        elif size_bytes > warning_threshold:
            self.prefect_engine.logger.warning(
                f"Batch {batch_num}: size {size_bytes:,} bytes approaching "
                f"Prefect parameter limit ({size_limit:,} bytes, controlled by PREFECT_SERVER_API_MAX_PARAMETER_SIZE). "
                f"Consider configuring batch_storage.type='s3' or 'local' for better performance, "
                f"or increase PREFECT_SERVER_API_MAX_PARAMETER_SIZE on Prefect Server.",
                extra={"job_run_id": job_run_id},
            )

        return {"type": BatchStorageType.INLINE.value, "data": batch_dict}

    # ─── Flow Run Monitoring ────────────────────────────────────────────

    def _wait_for_flow_runs(self, *, flow_runs: list[FlowRun], job_run_id: str) -> None:
        """
        Wait for all flow runs to complete concurrently with fail-fast cancellation.

        Uses Prefect's built-in wait_for_flow_run() with asyncio.gather() for
        concurrent waiting (per Prefect docs pattern). On first failure, cancels
        all remaining pending flow runs.

        Args:
            flow_runs: List of FlowRun objects from run_deployment()
            job_run_id: Parent job run ID for logging context

        Raises:
            FlowExecutionFailedException: If any flow run fails or times out
        """
        # Run async waiting in event loop (Prefect docs pattern)
        asyncio.run(self._wait_for_flow_runs_async(flow_runs=flow_runs, job_run_id=job_run_id))

    async def _wait_for_flow_runs_async(self, *, flow_runs: list[FlowRun], job_run_id: str) -> None:
        """
        Async implementation of concurrent flow run waiting.

        Follows Prefect documentation pattern:
        https://docs.prefect.io/llms-full.txt lines 77865-77880
        """
        completed_count = 0
        failed_info = []

        try:
            # Create coroutines for all flow runs (concurrent waiting)
            coros = [
                wait_for_flow_run(
                    flow_run_id=flow_run.id,
                    timeout=10800,  # 3 hours timeout per batch
                    log_states=True,  # Log state transitions
                )
                for flow_run in flow_runs
            ]

            # Wait for all concurrently
            finished_runs = await asyncio.gather(*coros, return_exceptions=True)

            # Process results
            for batch_num, (flow_run, result) in enumerate(zip(flow_runs, finished_runs, strict=True)):
                if isinstance(result, Exception):
                    # Exception during wait (timeout, connection error, etc.)
                    failed_info.append(
                        {
                            "batch_num": batch_num,
                            "run_id": str(flow_run.id),
                            "message": str(result),
                        }
                    )
                    self.prefect_engine.logger.error(
                        f"Error waiting for batch {batch_num} (flow_run={flow_run.id}): {result}",
                        extra={"job_run_id": job_run_id},
                        exc_info=True,
                    )
                elif isinstance(result, FlowRun) and result.state is not None and result.state.is_completed():
                    completed_count += 1
                    self.prefect_engine.logger.info(
                        f"Batch {batch_num} completed (flow_run={flow_run.id})", extra={"job_run_id": job_run_id}
                    )
                elif (
                    isinstance(result, FlowRun)
                    and result.state is not None
                    and (result.state.is_failed() or result.state.is_crashed())
                ):
                    # Handle both Failed and Crashed states as failures
                    state_type = "CRASHED" if result.state.is_crashed() else "FAILED"
                    failed_info.append(
                        {
                            "batch_num": batch_num,
                            "run_id": str(flow_run.id),
                            "message": result.state.message or f"Flow {state_type.lower()}",
                        }
                    )
                    self.prefect_engine.logger.error(
                        f"Batch {batch_num} {state_type} (flow_run={flow_run.id}): {result.state.message}",
                        extra={"job_run_id": job_run_id},
                    )
                elif isinstance(result, FlowRun) and result.state is not None and result.state.is_cancelled():
                    self.prefect_engine.logger.warning(
                        f"Batch {batch_num} was cancelled (flow_run={flow_run.id})", extra={"job_run_id": job_run_id}
                    )

            # If any failures, cancel remaining and raise
            if failed_info:
                # Cancel any still-running flows
                await self._cancel_remaining_runs_async(flow_runs=flow_runs, job_run_id=job_run_id)

                self._raise_failure(
                    failed_info=failed_info, completed_count=completed_count, total_count=len(flow_runs)
                )

        except FlowExecutionFailedException:
            raise
        except Exception as e:
            self.prefect_engine.logger.error(
                f"Unexpected error during flow run waiting: {e}",
                extra={"job_run_id": job_run_id},
                exc_info=True,
            )
            raise

    async def _cancel_remaining_runs_async(self, *, flow_runs: list[FlowRun], job_run_id: str) -> None:
        """
        Cancel all flow runs (async version for use within async context).

        Args:
            flow_runs: List of flow runs to cancel
            job_run_id: Parent job run ID for logging context
        """
        async with get_client() as client:
            for flow_run in flow_runs:
                try:
                    # Fetch current state to avoid cancelling finished runs
                    current_run = await client.read_flow_run(flow_run.id)
                    if current_run.state and current_run.state.is_final():
                        continue

                    await client.set_flow_run_state(
                        flow_run_id=flow_run.id,
                        state=Cancelled(message="Cancelled due to batch failure (fail-fast)"),
                    )
                    self.prefect_engine.logger.info(
                        f"Cancelled flow_run={flow_run.id}", extra={"job_run_id": job_run_id}
                    )
                except Exception as e:
                    self.prefect_engine.logger.warning(
                        f"Failed to cancel flow_run={flow_run.id}: {e}",
                        extra={"job_run_id": job_run_id},
                    )

    def _cancel_remaining_runs(self, *, flow_runs: list[FlowRun], failed_run_id: str, job_run_id: str) -> None:
        """
        Cancel remaining pending flow runs after a failure (sync version).

        Uses the synchronous Prefect client to avoid asyncio.run() conflicts
        inside Prefect's already-running event loop.

        Args:
            flow_runs: List of FlowRun objects to cancel
            failed_run_id: ID of the flow run that triggered cancellation
            job_run_id: Parent job run ID for logging context
        """
        self.prefect_engine.logger.warning(
            f"Triggering fail-fast cancellation for {len(flow_runs)} remaining flow runs",
            extra={"job_run_id": job_run_id},
        )

        # Use sync client — safe inside Prefect context (no asyncio.run needed)
        with get_client(sync_client=True) as client:
            for fr in flow_runs:
                try:
                    client.set_flow_run_state(
                        flow_run_id=fr.id,
                        state=Cancelled(message=f"Cancelled due to failure in flow run {failed_run_id}"),
                        force=True,
                    )
                    self.prefect_engine.logger.info(f"Cancelled flow run {fr.id}", extra={"job_run_id": job_run_id})
                except Exception as cancel_error:
                    self.prefect_engine.logger.warning(
                        f"Could not cancel flow run {fr.id}: {cancel_error}", extra={"job_run_id": job_run_id}
                    )

    @staticmethod
    def _raise_failure(*, failed_info: list[dict], completed_count: int, total_count: int) -> None:
        """Raise FlowExecutionFailedException with failure details."""
        error_details = "\n".join(
            [f"  - Batch {f['batch_num']} (flow_run={f['run_id']}): {f['message']}" for f in failed_info]
        )

        raise FlowExecutionFailedException(
            f"Batch execution failed. "
            f"Failed: {len(failed_info)}, "
            f"Completed: {completed_count}, "
            f"Total: {total_count}\n"
            f"Failure details:\n{error_details}"
        )

    # ─── Prefect Connectivity ───────────────────────────────────────────

    def _validate_prefect_connection(self) -> None:
        """
        Validate that Prefect Server is accessible.

        Uses the sync client to perform a health check.

        Raises:
            ValueError: If Prefect Server is not accessible
        """
        try:
            with get_client(sync_client=True) as client:
                health_error = client.api_healthcheck()
                if health_error:
                    raise ValueError(
                        f"Prefect Server health check failed: {health_error}. "
                        f"Ensure Prefect Server is running and PREFECT_API_URL is set correctly."
                    )

            self.prefect_engine.logger.info(
                f"Prefect Server connection verified (pool={self.work_pool_name}, deployment={self.deployment_name})"
            )
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(
                f"Cannot connect to Prefect Server: {e}. "
                f"Ensure Prefect Server is running and PREFECT_API_URL is set correctly. "
                f"For local setup, run: docker-compose -f docker/docker-compose.distributed.yml up -d"
            ) from e

    @staticmethod
    def _resolve_job_management_config_path() -> Path:
        config_path = os.getenv(EnvironmentVariables.DATASIFT_CONFIG_PATH)
        if config_path:
            return Path(config_path).resolve()
        return Path(__file__).resolve().parents[5] / "datasift-config.yaml"

    def _get_effective_job_management_env(self) -> dict[str, str]:
        """Resolve effective submitter-side job-management environment for worker propagation."""
        resolved_env: dict[str, str] = {}
        config_path = self._resolve_job_management_config_path()

        if config_path.exists():
            resolved_env[EnvironmentVariables.DATASIFT_CONFIG_PATH] = str(config_path)

        # Delegate to JobManagementFactory for resolving job management environment
        try:
            factory = JobManagementFactory.from_default_sources()
            job_management_env = factory.resolve_worker_env()
            resolved_env.update(job_management_env)
        except Exception as exc:
            logger.warning(f"Failed to resolve job management environment for work pool propagation: {exc}")

        return resolved_env

    def _build_container_env(self, *, base_env: dict[str, str], deployment_path: str | None) -> dict[str, str]:
        """Build container environment with required defaults."""
        env = base_env.copy()

        if EnvironmentVariables.PREFECT_API_URL not in env:
            env[EnvironmentVariables.PREFECT_API_URL] = os.getenv(
                EnvironmentVariables.PREFECT_API_URL,
                "http://prefect-server:4200/api",
            )
        if EnvironmentVariables.PREFECT_MODE not in env:
            env[EnvironmentVariables.PREFECT_MODE] = "server"
        if EnvironmentVariables.PYTHONPATH not in env:
            env[EnvironmentVariables.PYTHONPATH] = deployment_path or os.getcwd()
        if EnvironmentVariables.OLLAMA_HOST not in env:
            env[EnvironmentVariables.OLLAMA_HOST] = os.getenv(
                EnvironmentVariables.OLLAMA_HOST, "http://localhost:11434"
            )
        effective_job_management_env = self._get_effective_job_management_env()
        for env_key, env_value in effective_job_management_env.items():
            if env_key not in env:
                env[env_key] = env_value

        return env

    def _build_kubernetes_customizations(self, *, config: KubernetesWorkPoolConfig) -> list[dict[str, Any]]:
        """
        Build JSON Patch customizations for Kubernetes jobs.
        Prefect expects infrastructure overrides to be passed as JSON Patches.
        """
        customizations: list[dict[str, Any]] = []

        if config.volumes:
            customizations.append({"op": "add", "path": "/spec/template/spec/volumes", "value": config.volumes})

        if config.init_containers:
            customizations.append(
                {"op": "add", "path": "/spec/template/spec/initContainers", "value": config.init_containers}
            )

        if config.volume_mounts:
            customizations.append(
                {"op": "add", "path": "/spec/template/spec/containers/0/volumeMounts", "value": config.volume_mounts}
            )

        if config.working_dir:
            customizations.append(
                {"op": "add", "path": "/spec/template/spec/containers/0/workingDir", "value": config.working_dir}
            )

        if config.image_pull_secrets:
            customizations.append(
                {
                    "op": "add",
                    "path": "/spec/template/spec/imagePullSecrets",
                    "value": [{"name": secret_name} for secret_name in config.image_pull_secrets],
                }
            )

        customizations.append(
            {
                "op": "add",
                "path": "/spec/template/spec/containers/0/resources",
                "value": {
                    "requests": {
                        "cpu": config.cpu_request,
                        "memory": config.memory_request,
                    },
                    "limits": {
                        "cpu": config.cpu_limit,
                        "memory": config.memory_limit,
                    },
                },
            }
        )

        return customizations

    def _build_job_variables(self) -> dict[str, Any] | None:
        """Build deployment job variables from typed work pool config."""
        config = self.work_pool_runtime_config

        if isinstance(config, DockerWorkPoolConfig):
            job_vars: dict[str, Any] = {
                "image": config.image,
                "image_pull_policy": config.image_pull_policy,
                "env": self._build_container_env(
                    base_env=config.env,
                    deployment_path=config.deployment_path,
                ),
            }
            if config.networks:
                job_vars["networks"] = config.networks
            return job_vars

        if isinstance(config, KubernetesWorkPoolConfig):
            return {
                "image": config.image,
                "image_pull_policy": config.image_pull_policy,
                "namespace": config.namespace,
                "service_account_name": config.service_account_name,
                "finished_job_ttl": config.finished_job_ttl,
                "pod_watch_timeout_seconds": config.pod_watch_timeout_seconds,
                "stream_output": config.stream_output,
                "cpu_request": config.cpu_request,
                "cpu_limit": config.cpu_limit,
                "memory_request": config.memory_request,
                "memory_limit": config.memory_limit,
                "env": self._build_container_env(
                    base_env=config.env,
                    deployment_path=config.deployment_path,
                ),
            }

        if isinstance(config, ECSWorkPoolConfig):
            return {"image": config.image}

        if isinstance(config, ProcessWorkPoolConfig):
            # Process workers need environment variables passed via job_variables.
            # Start with config-provided env, then fill runtime defaults/overrides.
            return {
                "env": self._build_container_env(
                    base_env=config.env,
                    deployment_path=config.deployment_path,
                )
            }

        return None

    def _ensure_deployment_exists(self) -> None:
        """
        Ensure the batch subflow deployment exists in Prefect Server.

        Uses batch_subflow.deploy() — Prefect's recommended high-level API.
        This is idempotent: calling deploy() with the same name creates the
        deployment if it doesn't exist, or updates it if it does.

        For process work pools:
            No Docker image needed — workers use the local Python environment.

        For docker/kubernetes work pools:
            Users provide their image via work_pool_config["image"].
            The image must have datasift and all dependencies installed.

        This is called once during __init__, not per-batch.
        """
        from prefect import get_client

        from datasift.core.orchestration.prefect.batch_subflow import batch_subflow

        self.prefect_engine.logger.info(
            f"Ensuring deployment exists: {self.deployment_name} "
            f"(work_pool={self.work_pool_name}, type={self.work_pool_type})"
        )

        try:
            client = get_client(sync_client=True)

            # Inject volumes/initContainers/volumeMounts directly into the
            # work pool's base_job_template.  The KubernetesWorkerJobConfiguration
            # model does NOT have a 'customizations' field, so JSON-Patch style
            # overrides passed as job_variables are silently dropped.  The only
            # reliable approach is to embed these resources into the job_manifest
            # that lives inside the template itself.
            if isinstance(self.work_pool_runtime_config, KubernetesWorkPoolConfig):
                config = self.work_pool_runtime_config
                try:
                    if not self.work_pool_name:
                        raise ValueError("work_pool_name is required for KubernetesWorkPoolConfig")
                    pool = client.read_work_pool(self.work_pool_name)
                    base_template = pool.base_job_template
                    job_manifest = base_template.get("job_configuration", {}).get("job_manifest", {})
                    pod_spec = job_manifest.get("spec", {}).get("template", {}).get("spec", {})
                    needs_update = False

                    # Inject volumes
                    if config.volumes and pod_spec.get("volumes") != config.volumes:
                        pod_spec["volumes"] = config.volumes
                        needs_update = True

                    # Inject initContainers
                    if config.init_containers and pod_spec.get("initContainers") != config.init_containers:
                        pod_spec["initContainers"] = config.init_containers
                        needs_update = True

                    # Inject volumeMounts into the first container
                    if config.volume_mounts and pod_spec.get("containers"):
                        container = pod_spec["containers"][0]
                        if container.get("volumeMounts") != config.volume_mounts:
                            container["volumeMounts"] = config.volume_mounts
                            needs_update = True

                    # Inject workingDir into the first container
                    if config.working_dir and pod_spec.get("containers"):
                        container = pod_spec["containers"][0]
                        if container.get("workingDir") != config.working_dir:
                            container["workingDir"] = config.working_dir
                            needs_update = True

                    if needs_update:
                        from prefect.client.schemas.actions import WorkPoolUpdate

                        self.prefect_engine.logger.info(
                            f"Injecting infrastructure (volumes/initContainers/volumeMounts/workingDir) "
                            f"into work pool '{self.work_pool_name}' base_job_template."
                        )
                        client.update_work_pool(
                            work_pool_name=self.work_pool_name,
                            work_pool=WorkPoolUpdate(base_job_template=base_template),
                        )
                    else:
                        self.prefect_engine.logger.info(
                            f"Work pool '{self.work_pool_name}' base_job_template already has required infrastructure."
                        )
                except Exception as e:
                    self.prefect_engine.logger.warning(
                        f"Could not update work pool template for {self.work_pool_name}: {e}"
                    )

            # Check if deployment already exists
            try:
                existing = client.read_deployment_by_name(f"{batch_subflow.name}/{self.deployment_name}")
                self.prefect_engine.logger.info(f"Deployment exists: {self.deployment_name} (id={existing.id})")
                return
            except Exception:
                # Deployment doesn't exist, need to create it
                self.prefect_engine.logger.info(f"Deployment not found, will create: {self.deployment_name}")

            # Step 1: Register the flow (if not already registered)
            try:
                flow_obj = client.read_flow_by_name(batch_subflow.name)
                self.prefect_engine.logger.info(f"Flow already registered: {batch_subflow.name} (id={flow_obj.id})")
            except Exception:
                # Flow not registered - use client.create_flow() to register it
                self.prefect_engine.logger.info(f"Registering flow: {batch_subflow.name}")
                flow_id = client.create_flow(batch_subflow)
                self.prefect_engine.logger.info(f"Flow registered: {batch_subflow.name} (id={flow_id})")
                # Read the flow object for deployment creation
                flow_obj = client.read_flow_by_name(batch_subflow.name)

            # Step 2: Create deployment using client API
            # The entrypoint tells workers where to find the flow code
            if isinstance(self.work_pool_runtime_config, ProcessWorkPoolConfig):
                entrypoint = "datasift.core.orchestration.prefect.batch_subflow:batch_subflow"
            else:
                entrypoint = "datasift/core/orchestration/prefect/batch_subflow.py:batch_subflow"

            # For process workers: Determine where the flow code lives on the
            # WORKER's filesystem.
            #
            # Two scenarios:
            # 1. Local dev (guide Steps 1-4): submitter and worker share the same
            #    filesystem → os.getcwd() is correct.
            # 2. Docker (docker-compose): worker runs in a container where code is
            #    at a different path (e.g. /app/src/datasift_opensource/backend)
            #    → user must set deployment_path in their flow config.
            #
            # If deployment_path is None (default), we fall back to os.getcwd().
            if isinstance(self.work_pool_runtime_config, ProcessWorkPoolConfig):
                worker_code_dir = self.work_pool_runtime_config.deployment_path or os.getcwd()
                self.prefect_engine.logger.info(
                    f"Process work pool: worker code directory = {worker_code_dir}"
                    f" (source={'config' if self.work_pool_runtime_config.deployment_path else 'os.getcwd()'})"
                )

                deployment_params = {
                    "flow_id": flow_obj.id,
                    "name": self.deployment_name,
                    "work_pool_name": self.work_pool_name,
                    "entrypoint": entrypoint,
                    "path": worker_code_dir,
                    "pull_steps": [
                        {
                            "prefect.deployments.steps.set_working_directory": {
                                "directory": worker_code_dir,
                            }
                        }
                    ],
                }
            else:
                # Container-based workers need path for code deployment.
                # Default to the pre-baked path in the Docker image (/app/...)
                deployment_path = (
                    self.work_pool_runtime_config.deployment_path or BatchStrategyConstants.DEFAULT_DEPLOYMENT_PATH
                )
                self.prefect_engine.logger.info(
                    f"Container work pool: deployment path = {deployment_path}"
                    f" (source={'config' if self.work_pool_runtime_config.deployment_path else 'default'})"
                )
                deployment_params = {
                    "flow_id": flow_obj.id,
                    "name": self.deployment_name,
                    "work_pool_name": self.work_pool_name,
                    "entrypoint": entrypoint,
                    "path": deployment_path,
                    "pull_steps": [],
                }

            job_vars = self._build_job_variables()
            if job_vars:
                deployment_params["job_variables"] = job_vars

            if isinstance(self.work_pool_runtime_config, DockerWorkPoolConfig):
                docker_job_vars = self._build_job_variables() or {}
                self.prefect_engine.logger.info(
                    f"Configured Docker work pool with image: {self.work_pool_runtime_config.image}, "
                    f"networks: {self.work_pool_runtime_config.networks}, env vars: {len(docker_job_vars.get('env', {}))}"
                )
            elif isinstance(self.work_pool_runtime_config, KubernetesWorkPoolConfig):
                self.prefect_engine.logger.info(
                    f"Configured Kubernetes work pool with image: {self.work_pool_runtime_config.image}, "
                    f"namespace: {self.work_pool_runtime_config.namespace}, "
                    f"service_account: {self.work_pool_runtime_config.service_account_name}, "
                    f"resources: {self.work_pool_runtime_config.cpu_request}/{self.work_pool_runtime_config.cpu_limit} CPU, "
                    f"{self.work_pool_runtime_config.memory_request}/{self.work_pool_runtime_config.memory_limit} memory"
                )
            elif isinstance(self.work_pool_runtime_config, ECSWorkPoolConfig):
                self.prefect_engine.logger.info(
                    f"Configured ECS work pool with image: {self.work_pool_runtime_config.image}"
                )

            # Create deployment
            deployment_id = client.create_deployment(**deployment_params)

            self.prefect_engine.logger.info(f"Deployment created: {self.deployment_name} (id={deployment_id})")

        except Exception as e:
            # Log error with helpful instructions
            error_msg = (
                f"Failed to create deployment '{self.deployment_name}': {e}\n\n"
                f"Possible causes:\n"
                f"1. Work pool '{self.work_pool_name}' doesn't exist\n"
                f"2. Network/connectivity issues with Prefect Server\n"
                f"3. Flow registration failed\n\n"
                f"To create manually:\n"
                f"  docker exec -it $(docker ps -q -f name=prefect-worker | head -1) bash\n"
                f'  python -c "from datasift.core.orchestration.prefect.batch_subflow import batch_subflow; '
                f"batch_subflow.deploy(name='{self.deployment_name}', work_pool_name='{self.work_pool_name}', build=False, push=False)\"\n"
            )
            raise RuntimeError(error_msg) from e

    # ─── Cleanup ────────────────────────────────────────────────────────

    def _cleanup_batch_storage(self, *, job_run_id: str) -> None:
        """
        Clean up temporary batch data from storage after all batches complete.

        Best-effort cleanup — failures are logged but don't raise exceptions.

        Args:
            job_run_id: Job run ID for path namespacing
        """
        if self.batch_storage_type == BatchStorageType.LOCAL:
            try:
                import shutil

                batch_dir = os.path.join(self.batch_storage_path, job_run_id)
                if os.path.exists(batch_dir):
                    shutil.rmtree(batch_dir)
                    self.prefect_engine.logger.info(
                        f"Cleaned up batch storage: {batch_dir}", extra={"job_run_id": job_run_id}
                    )
            except Exception as e:
                self.prefect_engine.logger.warning(
                    f"Could not clean up batch storage: {e}", extra={"job_run_id": job_run_id}
                )

        elif self.batch_storage_type == BatchStorageType.S3:
            # S3 cleanup is more complex and should be done via lifecycle policies
            # or a separate cleanup process. Log a note for now.
            self.prefect_engine.logger.info(
                f"S3 batch data at s3://{self.batch_storage_bucket}/"
                f"{self.batch_storage_prefix}{job_run_id}/ can be cleaned up "
                f"via S3 lifecycle policies.",
                extra={"job_run_id": job_run_id},
            )

    # ─── Strategy Info ──────────────────────────────────────────────────

    def get_strategy_name(self) -> str:
        """Return strategy name for logging."""
        return f"work-pool-{self.work_pool_type}"
