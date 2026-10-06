"""Tests for cross-document request batching and concurrency in EmbeddingsOperator."""

import math
import random
import threading
import time
from typing import Any
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pytest

from docpipe.core.constants.constants import ExecutionStatus, Metrics
from docpipe.core.models.session_info import SessionInfo, session_info_var
from docpipe.core.operators.functional.embeddings import EmbeddingsOperator
from docpipe.core.ports.llm_embedding_port import LLMEmbeddingPort

_ADAPTER_FACTORY_PATH = "docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter"


def _vector_for(text: str) -> list[float]:
    """Deterministic 3-d vector derived from the text itself."""
    return [float(sum(map(ord, text)) % 997), float(len(text)), float(ord(text[0]))]


class _RecordingAdapter(LLMEmbeddingPort):
    """Embedding port double that records calls and measures in-flight concurrency."""

    def __init__(
        self,
        *,
        batch_size: int,
        max_concurrent_requests: int = 1,
        delay: float = 0.0,
        jitter: float = 0.0,
        fail_when: Any = None,
    ) -> None:
        self._batch_size = batch_size
        self._max_concurrent_requests = max_concurrent_requests
        self._delay = delay
        self._jitter = jitter
        self._fail_when = fail_when
        self._lock = threading.Lock()
        self._in_flight = 0
        self.max_in_flight = 0
        self.calls: list[list[str]] = []
        self.call_sessions: list[SessionInfo | None] = []

    def generate_embeddings(self, *, text: str) -> list[float]:
        return _vector_for(text)

    def generate_embeddings_batch(self, *, texts: list[str]) -> list[list[float]]:
        with self._lock:
            self.calls.append(list(texts))
            self.call_sessions.append(session_info_var.get())
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
        try:
            if self._delay or self._jitter:
                time.sleep(self._delay + random.uniform(0.0, self._jitter))
            if self._fail_when is not None and self._fail_when(texts):
                raise RuntimeError("provider unavailable")
            return [_vector_for(text) for text in texts]
        finally:
            with self._lock:
                self._in_flight -= 1

    def get_embedding_dimension(self) -> int:
        return 3

    def get_embedding_batch_size(self) -> int:
        return self._batch_size

    def get_max_concurrent_requests(self) -> int:
        return self._max_concurrent_requests


def _make_operator(*, adapter: LLMEmbeddingPort, **config: Any) -> EmbeddingsOperator:
    base_config: dict[str, Any] = {
        "provider": "litellm",
        "embeddings_column": "embeddings",
        "provider_config": {"model_id": "openai/text-embedding-3-small", "api_key": "<test-api-key>"},
    }
    base_config.update(config)
    with patch(_ADAPTER_FACTORY_PATH, return_value=adapter):
        return EmbeddingsOperator(base_config)


def _chunked_table(*, chunks_per_doc: list[list[Any]]) -> pa.Table:
    count = len(chunks_per_doc)
    return pa.table(
        {
            "id": [f"doc{i}" for i in range(count)],
            "name": [f"Document {i}" for i in range(count)],
            "content": [f"content {i}" for i in range(count)],
            "doc_id_hash": [f"hash{i}" for i in range(count)],
            "chunked_content": [
                [{"chunk": c} if isinstance(c, str) else c for c in chunks] for chunks in chunks_per_doc
            ],
        }
    )


def _unchunked_table(*, contents: list[str]) -> pa.Table:
    count = len(contents)
    return pa.table(
        {
            "id": [f"doc{i}" for i in range(count)],
            "name": [f"Document {i}" for i in range(count)],
            "content": contents,
            "doc_id_hash": [f"hash{i}" for i in range(count)],
        }
    )


class TestRequestCount:
    """Texts from all documents are packed into full requests of batch_size."""

    def test_chunked_request_count_spans_documents(self):
        adapter = _RecordingAdapter(batch_size=16)
        operator = _make_operator(adapter=adapter)
        chunks = [[f"d{d}-c{c}" for c in range(7)] for d in range(10)]

        result_tables, metadata = operator.transform(_chunked_table(chunks_per_doc=chunks))

        total_texts = 70
        assert len(adapter.calls) == math.ceil(total_texts / 16)
        assert [len(call) for call in adapter.calls] == [16, 16, 16, 16, 6]
        # Every text is sent exactly once, in document order
        assert [text for call in adapter.calls for text in call] == [t for doc in chunks for t in doc]
        assert metadata[Metrics.External.PROCESSED_DOCS] == 10
        assert result_tables[0].num_rows == 10

    def test_unchunked_request_count_spans_documents(self):
        adapter = _RecordingAdapter(batch_size=8)
        operator = _make_operator(adapter=adapter)

        operator.transform(_unchunked_table(contents=[f"document text {i}" for i in range(50)]))

        assert len(adapter.calls) == math.ceil(50 / 8)
        assert all(len(call) == 8 for call in adapter.calls[:-1])

    def test_empty_texts_are_not_sent(self):
        adapter = _RecordingAdapter(batch_size=4)
        operator = _make_operator(adapter=adapter)

        operator.transform(_chunked_table(chunks_per_doc=[["a1", "   ", "a2"], ["   "], ["b1"]]))

        assert [text for call in adapter.calls for text in call] == ["a1", "a2", "b1"]
        assert len(adapter.calls) == 1


class TestConcurrency:
    """At most max_concurrent_requests requests are in flight."""

    def test_in_flight_requests_never_exceed_limit(self):
        adapter = _RecordingAdapter(batch_size=2, max_concurrent_requests=3, delay=0.02)
        operator = _make_operator(adapter=adapter)

        operator.transform(_unchunked_table(contents=[f"text {i}" for i in range(40)]))

        assert len(adapter.calls) == 20
        assert adapter.max_in_flight <= 3
        assert adapter.max_in_flight > 1, "requests should actually overlap"

    def test_single_request_limit_is_sequential(self):
        adapter = _RecordingAdapter(batch_size=2, max_concurrent_requests=1, delay=0.005)
        operator = _make_operator(adapter=adapter)

        operator.transform(_unchunked_table(contents=[f"text {i}" for i in range(10)]))

        assert adapter.max_in_flight == 1

    def test_worker_threads_see_caller_session_info(self):
        adapter = _RecordingAdapter(batch_size=1, max_concurrent_requests=4, delay=0.005)
        operator = _make_operator(adapter=adapter)
        session = SessionInfo(job_id="job-1", job_run_id="run-1")
        token = session_info_var.set(session)
        try:
            operator.transform(_unchunked_table(contents=[f"text {i}" for i in range(8)]))
        finally:
            session_info_var.reset(token)

        assert len(adapter.call_sessions) == 8
        assert all(s is session for s in adapter.call_sessions)


class TestScatter:
    """Vectors are returned to the right documents in the right order."""

    @pytest.mark.parametrize("max_concurrent_requests", [1, 4])
    def test_chunked_vectors_land_on_their_documents(self, max_concurrent_requests):
        adapter = _RecordingAdapter(batch_size=3, max_concurrent_requests=max_concurrent_requests, jitter=0.01)
        operator = _make_operator(adapter=adapter)
        chunks: list[list[Any]] = [
            ["alpha", "beta", "gamma", "delta"],
            ["   ", "epsilon"],  # whitespace-only chunk -> zero vector
            [{"chunk": "zeta", "summary": "about zeta"}],
            ["eta", "theta", "iota", "kappa", "lambda"],
        ]

        result_tables, metadata = operator.transform(_chunked_table(chunks_per_doc=chunks))
        result = result_tables[0]

        expected = [
            [_vector_for(t) for t in ["alpha", "beta", "gamma", "delta"]],
            [[0.0, 0.0, 0.0], _vector_for("epsilon")],
            [_vector_for("abstract: about zeta\ncontent: zeta")],
            [_vector_for(t) for t in ["eta", "theta", "iota", "kappa", "lambda"]],
        ]
        assert result["embeddings"].to_pylist() == expected
        assert result["id"].to_pylist() == ["doc0", "doc1", "doc2", "doc3"]
        assert result["doc_id_hash"].to_pylist() == ["hash0", "hash1", "hash2", "hash3"]
        assert metadata[Metrics.External.PROCESSED_DOCS] == 4
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

    @pytest.mark.parametrize("max_concurrent_requests", [1, 4])
    def test_unchunked_vectors_land_on_their_documents(self, max_concurrent_requests):
        adapter = _RecordingAdapter(batch_size=2, max_concurrent_requests=max_concurrent_requests, jitter=0.01)
        operator = _make_operator(adapter=adapter)
        contents = ["first doc", "second doc", "   ", "fourth doc", "fifth doc"]

        result_tables, metadata = operator.transform(_unchunked_table(contents=contents))
        result = result_tables[0]

        expected = [
            _vector_for("first doc"),
            _vector_for("second doc"),
            [0.0, 0.0, 0.0],  # whitespace-only content -> zero vector with the model's dimension
            _vector_for("fourth doc"),
            _vector_for("fifth doc"),
        ]
        assert result["embeddings"].to_pylist() == expected
        assert metadata[Metrics.External.PROCESSED_DOCS] == 5

    def test_documents_without_content_fail_without_affecting_others(self):
        adapter = _RecordingAdapter(batch_size=4)
        operator = _make_operator(adapter=adapter)

        result_tables, metadata = operator.transform(
            _chunked_table(chunks_per_doc=[["a1", "a2"], [], ["c1"], [{"chunk": ""}]])
        )
        result = result_tables[0]

        assert result["id"].to_pylist() == ["doc0", "doc2"]
        assert result["embeddings"].to_pylist() == [[_vector_for("a1"), _vector_for("a2")], [_vector_for("c1")]]
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 2
        assert [d["id"] for d in metadata[Metrics.External.FAILED_DOCS]] == ["doc1", "doc3"]
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    def test_long_text_pieces_are_averaged(self):
        adapter = _RecordingAdapter(batch_size=2)
        # token_limit 5 -> char limit 20, overlap 0.2 -> 4 chars
        operator = _make_operator(adapter=adapter, token_limit=5)
        long_text = "abcdefghijklmnopqrstuvwxyz0123456789"
        pieces = EmbeddingsOperator._split_long_text(text=long_text, char_limit=20, overlap_chars=4)

        result_tables, _metadata = operator.transform(_chunked_table(chunks_per_doc=[["short", long_text, "tail"]]))

        assert pieces == ["abcdefghijklmnopqrst", "qrstuvwxyz0123456789"]
        expected_long = np.mean([_vector_for(p) for p in pieces], axis=0).tolist()
        assert result_tables[0]["embeddings"].to_pylist() == [
            [_vector_for("short"), expected_long, _vector_for("tail")]
        ]
        assert [text for call in adapter.calls for text in call] == ["short", *pieces, "tail"]


class TestRequestFailures:
    """A failing request fails exactly the documents whose texts it carried."""

    @pytest.mark.parametrize("max_concurrent_requests", [1, 3])
    def test_failed_request_fails_only_its_documents(self, max_concurrent_requests):
        # 2 chunks per document and batch_size 4 -> request k carries docs 2k and 2k+1
        adapter = _RecordingAdapter(
            batch_size=4,
            max_concurrent_requests=max_concurrent_requests,
            fail_when=lambda texts: "d3-c0" in texts,
        )
        operator = _make_operator(adapter=adapter)
        chunks = [[f"d{d}-c0", f"d{d}-c1"] for d in range(6)]

        result_tables, metadata = operator.transform(_chunked_table(chunks_per_doc=chunks))
        result = result_tables[0]

        assert result["id"].to_pylist() == ["doc0", "doc1", "doc4", "doc5"]
        assert result["doc_id_hash"].to_pylist() == ["hash0", "hash1", "hash4", "hash5"]
        assert result["embeddings"].to_pylist() == [[_vector_for(t) for t in chunks[d]] for d in (0, 1, 4, 5)]
        assert metadata[Metrics.External.PROCESSED_DOCS] == 4
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 2
        failed = metadata[Metrics.External.FAILED_DOCS]
        assert [d["id"] for d in failed] == ["doc2", "doc3"]
        assert all("provider unavailable" in d["reason"] for d in failed)
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value
        # Only the failing request was affected; every other request was sent once
        assert len(adapter.calls) == 3

    def test_document_spanning_a_failed_request_fails(self):
        # batch_size 3: doc0 = texts 0-1, doc1 = texts 2-4 (spans requests 0 and 1), doc2 = text 5
        adapter = _RecordingAdapter(batch_size=3, fail_when=lambda texts: "b3" in texts)
        operator = _make_operator(adapter=adapter)

        result_tables, metadata = operator.transform(
            _chunked_table(chunks_per_doc=[["a1", "a2"], ["b1", "b2", "b3"], ["c1"]])
        )

        # Request 1 = ["b2", "b3", "c1"] failed: doc1 and doc2 fail, doc0 succeeds
        assert result_tables[0]["id"].to_pylist() == ["doc0"]
        assert [d["id"] for d in metadata[Metrics.External.FAILED_DOCS]] == ["doc1", "doc2"]

    def test_vector_count_mismatch_fails_request(self):
        class _ShortAdapter(_RecordingAdapter):
            def generate_embeddings_batch(self, *, texts: list[str]) -> list[list[float]]:
                return super().generate_embeddings_batch(texts=texts)[:-1]

        operator = _make_operator(adapter=_ShortAdapter(batch_size=10))

        result_tables, metadata = operator.transform(_unchunked_table(contents=["one", "two"]))

        assert result_tables[0].num_rows == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 2
        assert "returned 1 vectors for 2 texts" in metadata[Metrics.External.FAILED_DOCS][0]["reason"]

    def test_context_length_error_keeps_actionable_message(self):
        class _ContextAdapter(_RecordingAdapter):
            def generate_embeddings_batch(self, *, texts: list[str]) -> list[list[float]]:
                raise ValueError("input length exceeds the context length")

        operator = _make_operator(adapter=_ContextAdapter(batch_size=10))

        _result_tables, metadata = operator.transform(_unchunked_table(contents=["one"]))

        assert "context length" in metadata[Metrics.External.FAILED_DOCS][0]["reason"]
        assert "Chunking operator" in metadata[Metrics.External.FAILED_DOCS][0]["reason"]


class TestAdapterLimits:
    """batch_size / max_concurrent_requests come from the adapter, with safe fallbacks."""

    def test_limits_read_from_adapter(self):
        operator = _make_operator(adapter=_RecordingAdapter(batch_size=7, max_concurrent_requests=5))

        assert operator._batch_size == 7
        assert operator._max_concurrent_requests == 5

    @pytest.mark.parametrize("bad_value", [0, -1, None, "8", True, 2.5])
    def test_invalid_adapter_limits_fall_back_to_defaults(self, bad_value):
        adapter = _RecordingAdapter(batch_size=1)
        adapter._batch_size = bad_value
        adapter._max_concurrent_requests = bad_value

        operator = _make_operator(adapter=adapter)

        assert operator._batch_size == 32
        assert operator._max_concurrent_requests == 1
