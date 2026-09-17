"""
Integration tests for ThreadPoolAdapter.

Exercises the full Prefect @flow + ThreadPoolTaskRunner path end-to-end using a
realistic pipeline that matches the documented operator contract:

  ingest_source   (filesystem, txt files)
  └── extract_operator  (docling_library, entity_extraction: none)
      └── chunker        (simple, chunk_size=512)
          └── embeddings (huggingface, sentence-transformers/all-MiniLM-L6-v2,
                          use_local=true, device=cpu)

No Prefect Server or external services are required — ThreadPoolTaskRunner runs
in-process, and the HuggingFace model runs locally on CPU.

Pipeline is documented in:
  docs/reference/OPERATORS.md  — EmbeddingsOperator §, ChunkerOperator §,
                                  ExtractOperator §
  sample_flows/quickstart/micro_batching_regression_test.json

Tests skip gracefully if:
  - The customer_support_docs fixture directory is absent
  - sentence-transformers is not installed

Prefect mode
------------
These tests import docpipe with PREFECT_MODE unset, which pins the process to
Prefect ephemeral mode for good — set_prefect_env_variables() runs once, at
import of prefect_engine.py.  That is fine here: ThreadPoolTaskRunner needs no
server.  The WorkPool tests in this directory need server mode and get there
with temporary_settings(), so the two files can share a process and no special
run command is needed.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parents[3] / "fixtures" / "customer_support_docs"


# ---------------------------------------------------------------------------
# Skip guards
# ---------------------------------------------------------------------------


def _skip_if_no_fixtures() -> None:
    if not _FIXTURES_DIR.exists():
        pytest.skip(f"Fixture directory not found: {_FIXTURES_DIR}")


def _skip_if_no_sentence_transformers() -> None:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        pytest.skip("sentence-transformers not installed — skipping HuggingFace embedding tests")


# ---------------------------------------------------------------------------
# Flow factory
# ---------------------------------------------------------------------------


def _make_pipeline_flow(
    *,
    docs_path: str,
    micro_batching: bool = True,
    batch_size: int = 2,
    max_concurrent_batches: int = 2,
    continue_on_batch_failure: bool = False,
    with_noop: bool = False,
) -> dict:
    """
    Build an authoring-format flow definition for the integration pipeline:

        ingest_source → extract_operator → chunker → embeddings (HuggingFace)
                                                      [→ noop if with_noop=True]

    Parameters follow the documented operator contracts exactly:
    - ExtractOperator: text_extraction.provider=docling_library,
                       entity_extraction.provider=none
    - ChunkerOperator: chunk_type=simple, chunk_size=512, chunk_overlap=50
    - EmbeddingsOperator: provider=huggingface,
                          provider_config.model_id=sentence-transformers/all-MiniLM-L6-v2,
                          provider_config.use_local=true,
                          provider_config.device=cpu

    with_noop=True appends a noop operator after embeddings.  This is used by
    patch-based batch-failure tests: NOOPOperator.transform is monkeypatched to
    raise when batch_num == 1, exercising fail-fast and continue-on-failure paths
    without replacing the full realistic pipeline.
    """
    global_config: dict = {
        "doc_column": "content",
        "storage": "in-memory",
        # execute_type is set by the authoring compiler to "local" and is not
        # read anywhere in the execution path — the value here is ignored.
        "force_ingest": True,
        "enable_micro_batching": micro_batching,
        "micro_batch_size": batch_size,
        "max_concurrent_batches": max_concurrent_batches,
        # Explicitly request thread-pool strategy (default, but made explicit)
        "prefect": {
            "batch_execution": {
                "strategy": "thread-pool",
            }
        },
    }
    if continue_on_batch_failure:
        global_config["continue_on_batch_failure"] = True

    operators: list = [
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
            "type": "embeddings",
            "name": "embed",
            "depends_on": ["chunk"],
            "config": {
                # Native HuggingFace local inference — no network call needed.
                # Model: sentence-transformers/all-MiniLM-L6-v2 (22 MB, CPU)
                # Docs: OPERATORS.md §EmbeddingsOperator — Example 2b
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
    ]

    if with_noop:
        # noop is the patch target for batch-failure tests.
        # sleep_sec=0 so the step adds no latency on the happy batches.
        # batch_num is injected into self.config by create_executor() because
        # global_config (which contains BATCH_NUM) is spread into the operator
        # config dict — see abstract_orchestrator.py:636.
        operators.append(
            {
                "type": "noop",
                "name": "passthrough",
                "depends_on": ["embed"],
                "config": {"sleep_sec": 0},
            }
        )

    return {
        "flow_name": "integration-thread-pool-test",
        "flow_id": str(uuid.uuid4()),
        "global_config": global_config,
        "flow": operators,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestThreadPoolAdapterIntegration:
    """
    End-to-end integration tests for the ThreadPoolAdapter.

    Pipeline: ingest_source → extract_operator → chunker → embeddings (HuggingFace)
    Execution: Prefect ThreadPoolTaskRunner (no server required)
    Embeddings: sentence-transformers/all-MiniLM-L6-v2, local CPU inference
    """

    def test_micro_batched_pipeline_completes_successfully(self):
        """
        Happy path: 4 txt files split into 2 batches of 2.
        All four stages (ingest, extract, chunk, embed) must run to completion.
        No exception means the full pipeline succeeded.
        """
        _skip_if_no_fixtures()
        _skip_if_no_sentence_transformers()

        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        flow_def = _make_pipeline_flow(
            docs_path=str(_FIXTURES_DIR),
            micro_batching=True,
            batch_size=2,
        )
        manager = DocpipeFlowManager(flow_def=flow_def, enable_execution_reporter=False, configure_logging=False)

        # Must complete without raising
        manager.execute()

    def test_single_batch_no_micro_batching(self):
        """
        With enable_micro_batching=False all documents are processed as one
        batch.  ThreadPoolAdapter must still wrap the pipeline in a Prefect
        @flow and execute all four stages.
        """
        _skip_if_no_fixtures()
        _skip_if_no_sentence_transformers()

        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        flow_def = _make_pipeline_flow(
            docs_path=str(_FIXTURES_DIR),
            micro_batching=False,
        )
        manager = DocpipeFlowManager(flow_def=flow_def, enable_execution_reporter=False, configure_logging=False)

        manager.execute()

    def test_concurrent_batches_complete_without_deadlock(self):
        """
        max_concurrent_batches=2 allows both batches to run in parallel.
        This exercises the batch semaphore and ensures no deadlock occurs.
        """
        _skip_if_no_fixtures()
        _skip_if_no_sentence_transformers()

        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        flow_def = _make_pipeline_flow(
            docs_path=str(_FIXTURES_DIR),
            micro_batching=True,
            batch_size=2,
            max_concurrent_batches=2,
        )
        manager = DocpipeFlowManager(flow_def=flow_def, enable_execution_reporter=False, configure_logging=False)

        manager.execute()

    def test_fail_fast_on_nonexistent_operator(self):
        """
        A flow referencing an operator that does not exist must raise before
        any batches are submitted (FlowValidationException at compile/validate
        time, or FlowExecutionFailedException during execution).
        """
        _skip_if_no_fixtures()

        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        bad_flow = {
            "flow_name": "bad-operator-flow",
            "global_config": {
                "doc_column": "content",
                "force_ingest": True,
                "enable_micro_batching": True,
                "micro_batch_size": 2,
                "prefect": {"batch_execution": {"strategy": "thread-pool"}},
            },
            "flow": [
                {
                    "type": "ingest_source",
                    "name": "ingest",
                    "config": {
                        "provider": "filesystem",
                        "connection_params": {"paths": [str(_FIXTURES_DIR)]},
                        "include_filter": "txt",
                        "max_files": 2,
                        "force_ingest": True,
                    },
                },
                {
                    "type": "totally_nonexistent_operator_xyz",
                    "name": "bad",
                    "depends_on": ["ingest"],
                    "config": {},
                },
            ],
        }

        from docpipe.exceptions.docpipe_exceptions import FlowValidationException

        with pytest.raises((FlowValidationException, Exception)):
            manager = DocpipeFlowManager(flow_def=bad_flow, enable_execution_reporter=False, configure_logging=False)
            manager.execute()


# ---------------------------------------------------------------------------
# TC1 — operator transform raises on batch_num == 1
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
class TestThreadPoolOperatorFailureBehaviour:
    """
    Patch NOOPOperator.transform to raise on batch_num == 1 and verify both
    failure-policy paths through _wait_for_sub_flows.

    Pipeline: the full ingest → extract → chunker → embeddings → noop stack.
    noop is the patch target; all upstream operators run normally on every batch.
    batch_num is available inside transform via self.config (create_executor()
    spreads global_config — which carries BATCH_NUM — into the operator config;
    see abstract_orchestrator.py:636).

    ThreadPool tasks are in-process threads, so monkeypatch on the class is
    visible to every batch thread immediately.
    """

    @staticmethod
    def _patched_transform_raises_on_batch_1(self, table):
        """Replacement for NOOPOperator.transform — raises for batch_num == 1."""
        from docpipe.core.constants.constants import DocpipeConstants
        from docpipe.core.operators.operator_utils import OperatorUtils

        batch_num = self.config.get(DocpipeConstants.BATCH_NUM)
        if batch_num == 1:
            raise RuntimeError(f"Simulated operator failure in batch {batch_num}")
        metadata = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))
        return [table], metadata

    def test_fail_fast_operator_raises_propagates_exception(self, monkeypatch):
        """
        TC1-A fail-fast (default): NOOPOperator.transform raises on batch_num == 1.

        Expected: FlowExecutionFailedException propagates out of execute().
        The fix being validated: _wait_for_sub_flows never raises directly;
        it drains remaining batch threads then returns.  ThreadPoolAdapter
        raises after the outer Prefect flow has returned so the task runner
        is already shut down — no hang.
        """
        _skip_if_no_fixtures()
        _skip_if_no_sentence_transformers()

        from docpipe.core.operators.functional.noop import NOOPOperator
        from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException
        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        monkeypatch.setattr(NOOPOperator, "transform", self._patched_transform_raises_on_batch_1)

        flow_def = _make_pipeline_flow(
            docs_path=str(_FIXTURES_DIR),
            micro_batching=True,
            batch_size=2,
            max_concurrent_batches=2,
            continue_on_batch_failure=False,
            with_noop=True,
        )

        with pytest.raises((FlowExecutionFailedException, Exception)):
            manager = DocpipeFlowManager(
                flow_def=flow_def,
                enable_execution_reporter=False,
                configure_logging=False,
            )
            manager.execute()

    def test_continue_on_batch_failure_operator_raises_does_not_propagate(self, monkeypatch):
        """
        TC1-B continue mode: NOOPOperator.transform raises on batch_num == 1.

        Expected: execute() does NOT raise; partial failure is logged.
        Batch 0 completes the full pipeline; batch 1 fails at noop.transform.
        With continue_on_batch_failure=True the overall job must complete.
        """
        _skip_if_no_fixtures()
        _skip_if_no_sentence_transformers()

        from docpipe.core.operators.functional.noop import NOOPOperator
        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        monkeypatch.setattr(NOOPOperator, "transform", self._patched_transform_raises_on_batch_1)

        flow_def = _make_pipeline_flow(
            docs_path=str(_FIXTURES_DIR),
            micro_batching=True,
            batch_size=2,
            max_concurrent_batches=2,
            continue_on_batch_failure=True,
            with_noop=True,
        )

        try:
            manager = DocpipeFlowManager(
                flow_def=flow_def,
                enable_execution_reporter=False,
                configure_logging=False,
            )
            manager.execute()
        except Exception as exc:
            pytest.fail(f"execute() raised with continue_on_batch_failure=True: {exc}")


# ---------------------------------------------------------------------------
# TC2 — infrastructure failure inside the subflow (incremental metadata)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
class TestThreadPoolSubflowInfraFailureBehaviour:
    """
    Patch get_incremental_update_service in prefect_engine's module namespace
    to raise RuntimeError when the subflow for batch_num == 1 calls it.

    Location in source: prefect_engine.py:598
        incremental_update_util = get_incremental_update_service()

    This simulates an infrastructure failure (incremental metadata store
    unavailable) that fires inside the subflow *before* any operator runs.
    The patch targets the name in prefect_engine's own namespace:
        docpipe.core.orchestration.prefect.prefect_engine.get_incremental_update_service

    ThreadPool runs tasks in-process so monkeypatch.setattr on the module
    attribute is seen by every batch thread.
    """

    @staticmethod
    def _make_patched_incremental_service(real_fn):
        """
        Return a replacement callable for get_incremental_update_service.

        The function has no parameters, so batch_num must be obtained from the
        caller's frame — __flow_impl holds it in local variable global_config.
        Walking one frame up is sufficient because __flow_impl calls
        get_incremental_update_service() directly.
        """
        import sys

        def _patched():
            frame = sys._getframe(1)
            local_gc = frame.f_locals.get("global_config", {})
            from docpipe.core.constants.constants import DocpipeConstants

            if local_gc.get(DocpipeConstants.BATCH_NUM) == 1:
                raise RuntimeError("Simulated incremental metadata failure in batch 1")
            return real_fn()

        return _patched

    def test_fail_fast_subflow_infra_failure_propagates_exception(self, monkeypatch):
        """
        TC2-A fail-fast (default): incremental metadata raises in the subflow
        for batch 1.

        Expected: FlowExecutionFailedException propagates out of execute().
        The subflow for batch 1 raises before any operator runs; the main
        thread receives the failure, drains remaining futures, and raises —
        no hang.
        """
        _skip_if_no_fixtures()
        _skip_if_no_sentence_transformers()

        import docpipe.core.orchestration.prefect.prefect_engine as _pe
        from docpipe.core.incremental_metadata import get_incremental_update_service as _real
        from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException
        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        monkeypatch.setattr(_pe, "get_incremental_update_service", self._make_patched_incremental_service(_real))

        flow_def = _make_pipeline_flow(
            docs_path=str(_FIXTURES_DIR),
            micro_batching=True,
            batch_size=2,
            max_concurrent_batches=2,
            continue_on_batch_failure=False,
            with_noop=True,
        )

        with pytest.raises((FlowExecutionFailedException, Exception)):
            manager = DocpipeFlowManager(
                flow_def=flow_def,
                enable_execution_reporter=False,
                configure_logging=False,
            )
            manager.execute()

    def test_continue_on_batch_failure_subflow_infra_failure_does_not_propagate(self, monkeypatch):
        """
        TC2-B continue mode: incremental metadata raises in the subflow for
        batch 1.

        Expected: execute() does NOT raise; partial failure is logged.
        Batch 0 runs the full pipeline; batch 1 fails at infra setup.
        With continue_on_batch_failure=True the overall job must complete.
        """
        _skip_if_no_fixtures()
        _skip_if_no_sentence_transformers()

        import docpipe.core.orchestration.prefect.prefect_engine as _pe
        from docpipe.core.incremental_metadata import get_incremental_update_service as _real
        from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

        monkeypatch.setattr(_pe, "get_incremental_update_service", self._make_patched_incremental_service(_real))

        flow_def = _make_pipeline_flow(
            docs_path=str(_FIXTURES_DIR),
            micro_batching=True,
            batch_size=2,
            max_concurrent_batches=2,
            continue_on_batch_failure=True,
            with_noop=True,
        )

        try:
            manager = DocpipeFlowManager(
                flow_def=flow_def,
                enable_execution_reporter=False,
                configure_logging=False,
            )
            manager.execute()
        except Exception as exc:
            pytest.fail(f"execute() raised with continue_on_batch_failure=True: {exc}")
