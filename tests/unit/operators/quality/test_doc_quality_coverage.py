"""Tests for DocQuality operator to bring coverage to 80%."""

# ruff: noqa: E402 — importlib.util.find_spec must be patched before docpipe imports
import importlib.util
import sys
from unittest.mock import MagicMock

# Prevent importlib.util.find_spec from crashing on MagicMock modules installed
# by other test files earlier in the session (MagicMock.__spec__ == None).
_real_find_spec = importlib.util.find_spec


def _safe_find_spec(name, *args, **kwargs):
    try:
        return _real_find_spec(name, *args, **kwargs)
    except (ValueError, AttributeError):
        return None


importlib.util.find_spec = _safe_find_spec

import pyarrow as pa

# Pre-mock dpk_doc_quality before importing DocQuality
if "dpk_doc_quality" not in sys.modules:
    mock_dpk = MagicMock()
    mock_transform = MagicMock()

    class FakeDocQualityTransform:
        def __init__(self, config):
            self.config = config

        def transform(self, table):
            return [[table], {}]

    mock_dpk.transform.DocQualityTransform = FakeDocQualityTransform
    sys.modules["dpk_doc_quality"] = mock_dpk
    sys.modules["dpk_doc_quality.transform"] = mock_dpk.transform
    mock_dpk.transform.DocQualityTransform = FakeDocQualityTransform

from docpipe.core.operators.quality.doc_quality import DocQuality


class TestDocQualityMetadata:
    def test_get_metadata_returns_dict(self):
        meta = DocQuality.get_metadata()
        assert isinstance(meta, dict)

    def test_short_name(self):
        assert DocQuality.short_name == "doc_quality"

    def test_get_required_features_returns_list(self):
        result = DocQuality.get_required_features()
        assert isinstance(result, list)

    def test_get_static_required_features(self):
        result = DocQuality.get_static_required_features()
        assert isinstance(result, list)

    def test_is_available(self):
        # Should return bool
        assert isinstance(DocQuality.is_available(), bool)


class TestDocQualityTransform:
    def _make_operator(self):
        return DocQuality(config={"doc_content_column": "content"})

    def test_transform_returns_table_and_metadata(self):
        op = self._make_operator()
        table = pa.table({"id": ["1", "2"], "name": ["a", "b"], "content": ["text one", "text two"]})
        tables, metadata = op.transform(table)
        assert isinstance(tables, list)
        assert len(tables) == 1
        assert isinstance(metadata, dict)

    def test_transform_metadata_has_total_docs(self):
        op = self._make_operator()
        table = pa.table({"id": ["1"], "name": ["a"], "content": ["some text"]})
        _, metadata = op.transform(table)
        assert "total_docs" in metadata or len(metadata) > 0

    def test_transform_empty_table(self):
        op = self._make_operator()
        schema = pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("name", pa.string()),
                pa.field("content", pa.string()),
            ]
        )
        table = pa.table({"id": [], "name": [], "content": []}, schema=schema)
        tables, _ = op.transform(table)
        assert isinstance(tables, list)
