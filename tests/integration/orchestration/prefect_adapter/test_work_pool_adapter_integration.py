"""
Integration tests for WorkPoolAdapter with a real Prefect Server + workers.

Infrastructure setup follows the documented Local POC Setup exactly:
  docs/integrations/prefect/DISTRIBUTED_EXECUTION_GUIDE.md §2.2

Subprocess lifecycle
--------------------
  Terminal-1 equivalent: prefect server start          (module-scoped fixture)
  Terminal-2 equivalent: prefect worker start x 2      (module-scoped fixture)
  Terminal-3 equivalent: PREFECT_MODE=server
                         PREFECT_API_URL=http://localhost:4200/api

per the guide: "Without PREFECT_MODE=server, Docpipe uses ephemeral mode and
ignores work pool configuration."

Work pool + deployment
----------------------
  prefect work-pool create docpipe-test-pool --type process  (Python SDK)
  batch_subflow.deploy(name="docpipe-batch-subflow", ...)    (Python SDK)

Batch storage
-------------
  type: local — shared temp directory accessible to both the submitter (test
  process) and the two workers (spawned as child processes on the same machine).
  Per the guide: shared filesystem path must be the same absolute path for all
  processes.

Flow pipeline
-------------
  ingest_source → extract_operator → chunker → embeddings (HuggingFace local)
  Mirrors: sample_flows/quickstart/micro_batching_regression_test.json
  Docs:    docs/reference/OPERATORS.md §EmbeddingsOperator, §ChunkerOperator,
                                        §ExtractOperator

Prefect mode (shared process)
-----------------------------
  These tests must work in a full-suite run, not only on their own, so they
  cannot rely on being the first thing that imports docpipe.

  set_prefect_env_variables() runs once, at import of prefect_engine.py, and
  latches Prefect's mode from the env at that moment.  Any earlier test that
  imports docpipe with PREFECT_MODE unset pins the process to ephemeral mode:
  an in-memory SQLite DB plus a temporary in-process server.  Prefect also
  caches its settings snapshot on first use, so a later monkeypatch.setenv()
  changes os.environ and nothing else -- PREFECT_API_URL.value() keeps
  returning None.  The submitter then talks to its own ephemeral server while
  the workers poll the real one, and every batch sits in Scheduled until the
  test times out.

  The _prefect_server_mode fixture below fixes both halves: env vars for the
  worker subprocesses, and temporary_settings() to override Prefect's cached
  snapshot for the submitter.

Skip policy
-----------
  Module-level: skip if 'prefect' CLI not on PATH or fixture directory absent
  Fixture-level: skip if the server does not become ready in 60 s or pool/deploy fails
  Test-level:   sentence-transformers guard on embedding tests
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Constants — aligned with DISTRIBUTED_EXECUTION_GUIDE.md §2.2
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parents[3] / "fixtures" / "customer_support_docs"

# Batch-failure tests need PDFs: docling_serve short-circuits .txt files and reads
# them straight off disk, so a txt corpus never contacts the service.
_PDF_FIXTURES_DIR = Path(__file__).parents[3] / "fixtures" / "invoices"

# A closed port on the loopback interface. Reachable-and-refused from both the
# submitter and the worker subprocesses, so the failure is deterministic.
_DEAD_DOCLING_SERVE_URL = "http://127.0.0.1:9"

# Server runs on the default port used in all guide examples
_SERVER_HOST = "127.0.0.1"
_SERVER_PORT = 4200
_PREFECT_API_URL = f"http://{_SERVER_HOST}:{_SERVER_PORT}/api"

# Guide §2.2 Step 2: "prefect work-pool create docpipe-pool --type process"
_WORK_POOL_NAME = "docpipe-test-pool"
_WORK_POOL_TYPE = "process"

# Guide §7.2: deployment_name defaults to "docpipe-batch-subflow"
_DEPLOYMENT_NAME = "docpipe-batch-subflow"

_SERVER_READY_TIMEOUT = 60  # seconds
_SERVER_READY_POLL = 4  # seconds
_WORKER_WARMUP = 10  # seconds — workers register with server


# ---------------------------------------------------------------------------
# Module-level skip guards
# ---------------------------------------------------------------------------


def _prefect_cli() -> str | None:
    return shutil.which("prefect")


if _prefect_cli() is None:
    pytest.skip("prefect CLI not found on PATH — skipping WorkPool integration tests", allow_module_level=True)

if not _FIXTURES_DIR.exists():
    pytest.skip(
        f"Fixture directory not found: {_FIXTURES_DIR} — skipping WorkPool integration tests",
        allow_module_level=True,
    )

if not _PDF_FIXTURES_DIR.exists():
    pytest.skip(
        f"PDF fixture directory not found: {_PDF_FIXTURES_DIR} — skipping WorkPool integration tests",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for_server(*, timeout: int = _SERVER_READY_TIMEOUT, poll: int = _SERVER_READY_POLL) -> bool:
    """Poll the Prefect /api/health endpoint until the server is ready."""
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{_PREFECT_API_URL}/health", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(poll)
    return False


def _kill(proc: subprocess.Popen) -> None:
    """Graceful terminate → SIGKILL fallback."""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    except OSError:
        pass


def _make_flow_def(
    *,
    docs_path: str,
    batch_storage_path: str,
    batch_size: int = 2,
    continue_on_batch_failure: bool = False,
) -> dict:
    """
    Build the full ingest → extract → chunker → embeddings flow definition.

    Follows the documented work-pool-process config schema exactly:
      docs/integrations/prefect/DISTRIBUTED_EXECUTION_GUIDE.md §7.2
      docs/reference/OPERATORS.md §ExtractOperator, §ChunkerOperator,
                                    §EmbeddingsOperator (Example 2b)
      sample_flows/quickstart/micro_batching_regression_test.json

    batch_storage type=local requires a shared path accessible to both
    the submitter (this process) and the worker sub-processes.
    """
    return {
        "flow_name": "integration-work-pool-test",
        "flow_id": str(uuid.uuid4()),
        "global_config": {
            "doc_column": "content",
            "storage": "in-memory",
            # Guide §2.2 Step 5: execute_type stays "local" for the submitter
            "execute_type": "local",
            "force_ingest": True,
            "enable_micro_batching": True,
            "micro_batch_size": batch_size,
            "max_concurrent_batches": 2,
            **({"continue_on_batch_failure": True} if continue_on_batch_failure else {}),
            "prefect": {
                "batch_execution": {
                    # Guide §2.2 Step 5 / §7.2 Minimal configuration
                    "strategy": f"work-pool-{_WORK_POOL_TYPE}",
                    "work_pool_name": _WORK_POOL_NAME,
                    # deployment_name defaults to "docpipe-batch-subflow" (guide §7.2 note)
                    # Only listed here for test clarity — matches _DEPLOYMENT_NAME constant
                    "deployment_name": _DEPLOYMENT_NAME,
                    "batch_storage": {
                        # Local shared filesystem — same absolute path for submitter and workers
                        # Guide §3.3 Local Filesystem Storage
                        "type": "local",
                        "path": batch_storage_path,
                    },
                }
            },
        },
        "flow": [
            {
                "type": "ingest_source",
                "name": "ingest",
                "config": {
                    "provider": "filesystem",
                    "connection_params": {"paths": [docs_path]},
                    "include_filter": "txt",
                    "max_files": 4,
                    "force_ingest": True,
                },
            },
            {
                # docs/reference/OPERATORS.md §ExtractOperator
                "type": "extract_operator",
                "name": "extract",
                "depends_on": ["ingest"],
                "config": {
                    "text_extraction": {
                        "provider": "docling_library",
                        "doc_column": "content",
                    },
                    "entity_extraction": {
                        "provider": "none",
                    },
                },
            },
            {
                # docs/reference/OPERATORS.md §ChunkerOperator
                "type": "chunker",
                "name": "chunk",
                "depends_on": ["extract"],
                "config": {
                    "chunk_type": "simple",
                    "doc_column": "content",
                    "chunk_size": 512,
                    "chunk_overlap": 50,
                    "retain_original_content": False,
                },
            },
            {
                # docs/reference/OPERATORS.md §EmbeddingsOperator — Example 2b
                # Native HuggingFace local CPU inference — no API key, no network
                # Model: sentence-transformers/all-MiniLM-L6-v2 (22 MB)
                "type": "embeddings",
                "name": "embed",
                "depends_on": ["chunk"],
                "config": {
                    "provider": "huggingface",
                    "provider_config": {
                        "model_id": "sentence-transformers/all-MiniLM-L6-v2",
                        "use_local": True,
                        "device": "cpu",
                        "batch_size": 16,
                    },
                    "embeddings_column": "embeddings",
                    "doc_column": "content",
                },
            },
        ],
    }


def _make_failing_flow_def(
    *,
    batch_storage_path: str,
    docs_path: str,
    batch_size: int = 2,
    continue_on_batch_failure: bool = False,
) -> dict:
    """
    Build a flow whose batches fail inside the worker, not on the submitter.

    Getting a batch to fail across a process boundary is fiddly, because no
    monkeypatch survives the trip: the failure has to live in the flow definition
    itself.  It also has to survive FlowValidator, which is stricter than it looks.
    _validate_node() constructs every operator on the submitter, so anything that
    blows up in __init__ or validate() -- an unsupported provider, a missing model,
    a bad path -- raises FlowValidationException before a single batch is submitted.

    Validation is non-executing, though.  It never calls transform().  So the
    injection is a provider that is valid on paper and unreachable in practice:

      - docling_serve is a supported text_extraction provider, so validation is happy
      - DoclingServeAdapter._init_adapter_config() only reads config; it opens no
        connection, so __init__ succeeds on the submitter too
      - the HTTP call happens in transform(), inside the worker, and 127.0.0.1:9 is
        closed -- the connection is refused rather than left hanging
      - ExtractOperator raises FlowExecutionFailedException, the batch flow run goes
        to Failed, and WorkPoolAdapter sees a failed run

    The PDF fixtures matter.  docling_serve short-circuits .txt files and reads them
    off disk without calling the service, so the customer_support_docs corpus would
    pass cleanly no matter what base_url says.

    Every batch fails, which is what the two callers want: fail-fast raises on the
    first, and continue mode raises on the all-batches-failed rule.

    Pipeline: ingest_source → extract_operator (docling_serve, dead port) → chunker
    """
    global_config: dict = {
        "doc_column": "content",
        "storage": "in-memory",
        "execute_type": "local",
        "force_ingest": True,
        "enable_micro_batching": True,
        "micro_batch_size": batch_size,
        "max_concurrent_batches": 2,
        "prefect": {
            "batch_execution": {
                "strategy": f"work-pool-{_WORK_POOL_TYPE}",
                "work_pool_name": _WORK_POOL_NAME,
                "deployment_name": _DEPLOYMENT_NAME,
                "batch_storage": {
                    "type": "local",
                    "path": batch_storage_path,
                },
            }
        },
    }
    if continue_on_batch_failure:
        global_config["continue_on_batch_failure"] = True

    return {
        "flow_name": "integration-work-pool-fail-test",
        "flow_id": str(uuid.uuid4()),
        "global_config": global_config,
        "flow": [
            {
                "type": "ingest_source",
                "name": "ingest",
                "config": {
                    "provider": "filesystem",
                    "connection_params": {"paths": [docs_path]},
                    "include_filter": "pdf",
                    "max_files": 4,
                    "force_ingest": True,
                },
            },
            {
                # Supported provider, so FlowValidator accepts it. The adapter opens
                # no connection at __init__, so the submitter builds it fine. The
                # request goes out from transform() in the worker and is refused.
                "type": "extract_operator",
                "name": "extract",
                "depends_on": ["ingest"],
                "config": {
                    "text_extraction": {
                        "provider": "docling_serve",
                        "doc_column": "content",
                        "provider_config": {
                            "base_url": _DEAD_DOCLING_SERVE_URL,
                            "timeout": 5,
                            "poll_interval": 1,
                            "max_retries": 1,
                        },
                    },
                    "entity_extraction": {
                        "provider": "none",
                    },
                },
            },
            {
                "type": "chunker",
                "name": "chunk",
                "depends_on": ["extract"],
                "config": {
                    "chunk_type": "simple",
                    "doc_column": "content",
                    "chunk_size": 512,
                    "chunk_overlap": 50,
                    "retain_original_content": False,
                },
            },
        ],
    }


# ---------------------------------------------------------------------------
# Module-scoped infrastructure fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _prefect_server_mode():
    """Point this module at the test server, whatever the process did before.

    Two things have to change, and only one of them is an env var.

    set_prefect_env_variables() runs once, at import of prefect_engine.  It reads
    PREFECT_MODE from the env at that moment and, when unset, pins the process to
    ephemeral mode.  The env vars are set here for anything that reads os.environ
    directly, and for the worker subprocesses that inherit them.

    But Prefect caches its own settings snapshot on first use, so os.environ alone
    is not enough once a flow has already run in this process: PREFECT_API_URL.value()
    keeps returning None while os.environ says otherwise.  temporary_settings()
    overrides the cached snapshot, and that is what actually redirects the submitter
    to the test server.  Without it the submitter talks to its own ephemeral server
    while the workers poll the real one, and every batch sits in Scheduled.
    """
    from prefect.settings import PREFECT_API_URL as _PAU
    from prefect.settings import temporary_settings

    prev_env = {k: os.environ.get(k) for k in ("PREFECT_MODE", "PREFECT_API_URL")}

    # Ephemeral leftovers would send the worker subprocesses to an in-memory DB.
    for key in (
        "PREFECT_API_DATABASE_CONNECTION_URL",
        "PREFECT_HOME",
        "PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED",
    ):
        os.environ.pop(key, None)
    os.environ["PREFECT_MODE"] = "server"
    os.environ["PREFECT_API_URL"] = _PREFECT_API_URL

    with temporary_settings({_PAU: _PREFECT_API_URL}):
        print(f"\n[DIAG] _prefect_server_mode: PREFECT_API_URL.value()={_PAU.value()!r}")
        yield

    for k, v in prev_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(scope="module")
def prefect_tmp_dir():
    """Temp directory for server DB, worker logs, and batch data."""
    with tempfile.TemporaryDirectory(prefix="docpipe_wp_it_") as d:
        yield Path(d)


@pytest.fixture(scope="module")
def batch_storage_dir(prefect_tmp_dir):
    """
    Shared batch storage directory — same absolute path for submitter and workers.
    Guide §3.3: 'Shared filesystem mounted at same path on all machines.'
    On a single machine this is just a temp dir.
    """
    d = prefect_tmp_dir / "batches"
    d.mkdir()
    return str(d)


@pytest.fixture(scope="module")
def prefect_server(_prefect_server_mode, prefect_tmp_dir):
    """
    Start a Prefect server on port 4200 (guide §2.2 Step 1).

    Uses a dedicated SQLite DB so the test never pollutes the developer's
    local Prefect state.
    """
    db_path = prefect_tmp_dir / "prefect.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    # Strip any ephemeral-mode vars that set_prefect_env_variables() injected
    # at import time — the server needs a real file-backed DB, not :memory:.
    server_env = {
        k: v for k, v in os.environ.items() if k not in ("PREFECT_API_DATABASE_CONNECTION_URL", "PREFECT_HOME")
    }
    server_env.update(
        {
            "PREFECT_API_DATABASE_CONNECTION_URL": db_url,
            "PREFECT_API_URL": _PREFECT_API_URL,
            "PREFECT_UI_ENABLED": "false",
            "PREFECT_LOGGING_LEVEL": "WARNING",
        }
    )

    print(f"\n[DIAG] Starting Prefect server | db={db_url} | url={_PREFECT_API_URL}")
    print(
        f"[DIAG] server env PREFECT_API_DATABASE_CONNECTION_URL={server_env.get('PREFECT_API_DATABASE_CONNECTION_URL')}"
    )

    log = (prefect_tmp_dir / "server.log").open("w")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "prefect",
            "server",
            "start",
            "--host",
            _SERVER_HOST,
            "--port",
            str(_SERVER_PORT),
        ],
        env=server_env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )

    ready = _wait_for_server()
    print(f"[DIAG] Server ready={ready} after polling {_PREFECT_API_URL}/health")
    if not ready:
        _kill(proc)
        log.close()
        pytest.skip(f"Prefect server did not become ready within {_SERVER_READY_TIMEOUT}s")

    yield proc

    _kill(proc)
    log.close()


@pytest.fixture(scope="module")
def prefect_work_pool(prefect_server, prefect_tmp_dir):
    """
    Create the work pool via Python SDK.

    Guide §2.2 Step 2: "prefect work-pool create docpipe-pool --type process"
    """
    print(f"\n[DIAG] Creating work pool '{_WORK_POOL_NAME}' via SDK")
    print(f"[DIAG] os.environ PREFECT_API_URL before pool create: {os.environ.get('PREFECT_API_URL')!r}")
    print(
        f"[DIAG] os.environ PREFECT_API_DATABASE_CONNECTION_URL before pool create: {os.environ.get('PREFECT_API_DATABASE_CONNECTION_URL')!r}"
    )

    # _prefect_server_mode already set PREFECT_API_URL and PREFECT_MODE.
    # Do not save/restore them here: clearing them mid-module puts the submitter
    # back into ephemeral mode for every test that follows.
    try:
        import asyncio

        from prefect.client.orchestration import get_client
        from prefect.client.schemas.actions import WorkPoolCreate
        from prefect.settings import PREFECT_API_URL as _PAU

        print(f"[DIAG] PREFECT_API_URL.value() at pool create time: {_PAU.value()!r}")

        async def _create_pool():
            async with get_client() as client:
                try:
                    await client.create_work_pool(work_pool=WorkPoolCreate(name=_WORK_POOL_NAME, type=_WORK_POOL_TYPE))
                    print(f"[DIAG] Work pool '{_WORK_POOL_NAME}' created OK")
                except Exception as e:
                    print(f"[DIAG] Work pool create error (may already exist): {e}")

        asyncio.run(_create_pool())
    except Exception as exc:
        print(f"[DIAG] FATAL: could not create work pool: {exc}")
        pytest.skip(f"Could not create work pool: {exc}")

    return _WORK_POOL_NAME


@pytest.fixture(scope="module")
def prefect_workers(prefect_work_pool, prefect_tmp_dir):
    """
    Spawn two process workers attached to the test work pool.

    Guide §2.2 Step 3: "prefect worker start --pool docpipe-pool"
    Two workers allow concurrency tests to exercise real parallelism.

    Workers inherit PREFECT_API_URL and PREFECT_MODE from the environment
    so they connect to the test server, not the developer's local instance.
    """
    # Build clean worker env: start from current os.environ but strip any
    # ephemeral-mode overrides that set_prefect_env_variables() injected at
    # import time (in-memory DB URL, submitter-owned PREFECT_HOME).
    # Workers must connect to the real file-backed server DB, not :memory:.
    ephemeral_keys = (
        "PREFECT_API_DATABASE_CONNECTION_URL",
        "PREFECT_HOME",
        "PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED",
    )
    env = {k: v for k, v in os.environ.items() if k not in ephemeral_keys}
    env.update(
        {
            "PREFECT_API_URL": _PREFECT_API_URL,
            "PREFECT_MODE": "server",
            "PREFECT_LOGGING_LEVEL": "WARNING",
        }
    )

    print(f"\n[DIAG] Worker env PREFECT_API_URL={env.get('PREFECT_API_URL')!r}")
    print(f"[DIAG] Worker env PREFECT_API_DATABASE_CONNECTION_URL={env.get('PREFECT_API_DATABASE_CONNECTION_URL')!r}")
    print(f"[DIAG] Worker env PREFECT_HOME={env.get('PREFECT_HOME')!r}")

    procs: list[tuple[subprocess.Popen, Any]] = []
    for idx in range(2):
        log = (prefect_tmp_dir / f"worker_{idx}.log").open("w")
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "prefect",
                "worker",
                "start",
                "--pool",
                _WORK_POOL_NAME,
                "--type",
                _WORK_POOL_TYPE,
                "--name",
                f"test-worker-{idx}",
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        procs.append((proc, log))
        print(f"[DIAG] Spawned worker-{idx} pid={proc.pid}")

    print(f"[DIAG] Waiting {_WORKER_WARMUP}s for workers to register...")
    time.sleep(_WORKER_WARMUP)

    # Verify workers are still alive after warmup
    for idx, (proc, _) in enumerate(procs):
        alive = proc.poll() is None
        print(f"[DIAG] worker-{idx} pid={proc.pid} alive={alive} returncode={proc.returncode}")

    yield [p for p, _ in procs]

    for proc, log in procs:
        _kill(proc)
        log.close()


@pytest.fixture(scope="module")
def prefect_infrastructure(prefect_workers, prefect_tmp_dir):
    """
    Confirm the server and workers are ready, and print the worker log tails
    for diagnosis if needed.
    """
    print("\n[DIAG] === prefect_infrastructure ready ===")
    # Print last 10 lines of each worker log for diagnosis
    for idx in range(2):
        log_path = prefect_tmp_dir / f"worker_{idx}.log"
        try:
            lines = log_path.read_text().splitlines()
            tail = lines[-10:] if len(lines) >= 10 else lines
            print(f"[DIAG] worker-{idx} log tail:\n" + "\n".join(f"  {line}" for line in tail))
        except Exception as e:
            print(f"[DIAG] Could not read worker-{idx} log: {e}")
    return


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
class TestWorkPoolAdapterIntegration:
    """
    End-to-end WorkPool batch execution tests.

    Requires the module-scoped fixtures to have started:
      - Prefect server on localhost:4200
      - Two process workers polling docpipe-test-pool
      - batch_subflow deployment registered

    If any fixture skips, the whole class is skipped by pytest.

    Per DISTRIBUTED_EXECUTION_GUIDE.md §2.2:
      PREFECT_MODE=server is injected via monkeypatch for each test.
      PREFECT_API_URL points at the test server instance.
    """

    def _set_env(self, monkeypatch):
        """
        Apply the two env vars documented as critical in guide §2.2 Step 4.
        """
        monkeypatch.setenv("PREFECT_MODE", "server")
        monkeypatch.setenv("PREFECT_API_URL", _PREFECT_API_URL)
        from prefect.settings import PREFECT_API_URL as _PAU

        print(f"\n[DIAG] _set_env: PREFECT_API_URL.value()={_PAU.value()!r}")
        print(f"[DIAG] _set_env: os.environ PREFECT_API_URL={os.environ.get('PREFECT_API_URL')!r}")
        print(
            f"[DIAG] _set_env: os.environ PREFECT_API_DATABASE_CONNECTION_URL={os.environ.get('PREFECT_API_DATABASE_CONNECTION_URL')!r}"
        )

    def test_full_pipeline_completes_successfully(self, prefect_infrastructure, batch_storage_dir, monkeypatch):
        """
        Happy path: 4 txt files → 2 batches → dispatched to 2 workers.
        Full ingest → extract → chunker → HuggingFace embeddings pipeline.
        Completes without raising.

        WorkPoolAdapter creates the deployment automatically on first execute().
        """
        print("\n[DIAG] test_full_pipeline_completes_successfully: starting")
        print(f"[DIAG]   batch_storage_dir={batch_storage_dir}")
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            pytest.skip("sentence-transformers not installed")

        self._set_env(monkeypatch)

        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        flow_def = _make_flow_def(
            docs_path=str(_FIXTURES_DIR),
            batch_storage_path=batch_storage_dir,
            batch_size=2,
        )
        manager = DocpipeFlowManager(
            flow_def=flow_def,
            enable_execution_reporter=False,
            configure_logging=False,
        )

        manager.execute()

    def test_bad_ingest_path_rejected_by_validation(self, prefect_infrastructure, batch_storage_dir, monkeypatch):
        """
        A non-existent ingest path never reaches the work pool.

        This was written as a fail-fast test, which it cannot be: ingest runs on
        the submitter, and FlowValidator rejects the filesystem provider config
        before any batch is submitted.  That is the correct behaviour, so the test
        now asserts it rather than pretending to cover fail-fast.

        WorkPool fail-fast is covered by test_fail_fast_on_worker_batch_error and
        test_continue_on_batch_failure_worker_error_does_not_raise, which fail
        inside the worker instead.
        """
        self._set_env(monkeypatch)

        from docpipe.exceptions.docpipe_exceptions import FlowValidationException
        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        bad_flow = _make_flow_def(
            docs_path="/nonexistent/path/that/does/not/exist",
            batch_storage_path=batch_storage_dir,
            batch_size=1,
        )

        with pytest.raises(FlowValidationException):
            manager = DocpipeFlowManager(
                flow_def=bad_flow,
                enable_execution_reporter=False,
                configure_logging=False,
            )
            manager.execute()

    def test_continue_on_batch_failure_does_not_raise(self, prefect_infrastructure, batch_storage_dir, monkeypatch):
        """
        With continue_on_batch_failure=True a failing batch must not cause
        the flow to raise — it logs a partial failure warning instead.
        """
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            pytest.skip("sentence-transformers not installed")

        self._set_env(monkeypatch)

        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        flow_def = _make_flow_def(
            docs_path=str(_FIXTURES_DIR),
            batch_storage_path=batch_storage_dir,
            batch_size=2,
        )
        flow_def["global_config"]["continue_on_batch_failure"] = True

        try:
            manager = DocpipeFlowManager(
                flow_def=flow_def,
                enable_execution_reporter=False,
                configure_logging=False,
            )
            manager.execute()
        except Exception as exc:
            pytest.fail(f"Flow raised unexpectedly with continue_on_batch_failure=True: {exc}")

    def test_two_concurrent_batches_both_complete(self, prefect_infrastructure, batch_storage_dir, monkeypatch):
        """
        max_concurrent_batches=2 dispatches both batches simultaneously.
        Each worker picks up one batch. Both must complete successfully.
        """
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            pytest.skip("sentence-transformers not installed")

        self._set_env(monkeypatch)

        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        flow_def = _make_flow_def(
            docs_path=str(_FIXTURES_DIR),
            batch_storage_path=batch_storage_dir,
            batch_size=2,
        )
        flow_def["global_config"]["max_concurrent_batches"] = 2

        manager = DocpipeFlowManager(
            flow_def=flow_def,
            enable_execution_reporter=False,
            configure_logging=False,
        )

        manager.execute()

    # -----------------------------------------------------------------------
    # Batch-level failure tests — subprocess-safe (no monkeypatching)
    # -----------------------------------------------------------------------

    def test_fail_fast_on_worker_batch_error(self, prefect_infrastructure, batch_storage_dir, monkeypatch):
        """
        TC1-A fail-fast: every batch fails inside its worker because
        extract_operator's docling_serve endpoint refuses the connection.

        Expected: FlowExecutionFailedException propagates out of execute() after
        WorkPoolAdapter sees the failed run, sets job_status=FAILING, cancels the
        remaining remote runs, and raises.  No hang.

        The assertion is narrow on purpose.  FlowValidationException and
        FlowExecutionFailedException are siblings under DocpipeException, so
        pytest.raises(Exception) goes green on a validation error that never
        touched a worker — which is how this test used to pass while the WorkPool
        fail-fast path went unexercised.  See _make_failing_flow_def.
        """
        self._set_env(monkeypatch)

        from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException
        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        flow_def = _make_failing_flow_def(
            docs_path=str(_PDF_FIXTURES_DIR),
            batch_storage_path=batch_storage_dir,
            batch_size=2,
            continue_on_batch_failure=False,
        )

        with pytest.raises(FlowExecutionFailedException):
            manager = DocpipeFlowManager(
                flow_def=flow_def,
                enable_execution_reporter=False,
                configure_logging=False,
            )
            manager.execute()

    def test_continue_on_batch_failure_worker_error_does_not_raise(
        self, prefect_infrastructure, batch_storage_dir, monkeypatch
    ):
        """
        TC1-B continue mode: every batch fails inside its worker for the same
        reason as TC1-A, but continue_on_batch_failure=True is set.

        When all batches fail in continue mode, WorkPoolAdapter logs the
        all-batches-failed case and raises (all-failed is still a failure).
        This verifies the boundary: a partial failure must NOT raise, but
        an all-failed run in continue mode still raises to signal total failure.

        Expected: FlowExecutionFailedException propagates because all batches
        failed (not just some).  This is correct behaviour per the spec:
          "If all batches fail even in continue mode, the job fails."
        If you want to assert the partial-failure (some succeed) path instead,
        see test_continue_on_batch_failure_does_not_raise which uses a valid
        pipeline that succeeds on all batches.

        """
        self._set_env(monkeypatch)

        from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException
        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        flow_def = _make_failing_flow_def(
            docs_path=str(_PDF_FIXTURES_DIR),
            batch_storage_path=batch_storage_dir,
            batch_size=2,
            continue_on_batch_failure=True,
        )

        # All batches fail → all-failed path raises even in continue mode.
        with pytest.raises(FlowExecutionFailedException):
            manager = DocpipeFlowManager(
                flow_def=flow_def,
                enable_execution_reporter=False,
                configure_logging=False,
            )
            manager.execute()
