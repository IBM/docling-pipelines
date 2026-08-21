"""Unit tests for DocQuality operator."""

import pyarrow as pa

from docpipe.core.constants.constants import Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.doc_quality import DEFAULT_TEXT_LANG, TEXT_LANG_KEY, DocQuality

EXPECTED_OUTPUT_COLUMNS = [
    "docq_total_words",
    "docq_mean_word_len",
    "docq_symbol_to_word_ratio",
    "docq_sentence_count",
    "docq_lorem_ipsum_ratio",
    "docq_contain_bad_word",
    "docq_bullet_point_ratio",
    "docq_curly_bracket_ratio",
    "docq_ellipsis_line_ratio",
    "docq_alphabet_word_ratio",
    "docq_contain_common_en_words",
]


def make_table(rows: list[str] | None = None) -> pa.Table:
    rows = rows or ["The quick brown fox jumps over the lazy dog.", "Hello world."]
    return pa.table({"id": [str(i) for i in range(len(rows))], "content": rows})


def make_operator(*, doc_content_column: str = "content", text_lang: str = "en") -> DocQuality:
    return DocQuality({"doc_content_column": doc_content_column, "text_lang": text_lang})


def test_get_metadata_returns_dict():
    """get_metadata() returns a dictionary."""
    assert isinstance(DocQuality.get_metadata(), dict)


def test_get_metadata_text_lang_attribute():
    """text_lang is present in attributes, optional, with the correct default."""
    meta = DocQuality.get_metadata()
    assert OperatorConstants.Config.ATTRIBUTES in meta
    assert TEXT_LANG_KEY in meta[OperatorConstants.Config.ATTRIBUTES]
    attr = meta[OperatorConstants.Config.ATTRIBUTES][TEXT_LANG_KEY]
    assert attr[OperatorConstants.Config.REQUIRED] is False
    assert attr[OperatorConstants.Config.DEFAULT] == DEFAULT_TEXT_LANG


# ---------------------------------------------------------------------------
# transform()
# ---------------------------------------------------------------------------


def test_transform_output_shape():
    """transform() adds all 11 docq_ columns, preserves input columns, and keeps row count."""
    table = make_table(["First doc.", "Second doc.", "Third doc."])
    tables, metadata = make_operator().transform(table)
    result = tables[0]
    assert result.num_rows == 3
    for col in table.column_names:
        assert col in result.column_names
    for col in EXPECTED_OUTPUT_COLUMNS:
        assert col in result.column_names, f"Missing column: {col}"
    assert metadata[Metrics.External.PROCESSED_DOCS] == 3
    assert metadata[Metrics.External.PROCESSED_ROWS] == 3


def test_transform_empty_table():
    """transform() handles an empty table without error and returns no rows."""
    table = pa.table({"id": pa.array([], type=pa.string()), "content": pa.array([], type=pa.string())})
    tables, metadata = make_operator().transform(table)
    assert tables[0].num_rows == 0
    assert metadata[Metrics.External.PROCESSED_DOCS] == 0


def test_transform_custom_doc_column():
    """transform() reads from a custom doc_content_column when configured."""
    table = pa.table({"id": ["1"], "body": ["The cat sat on the mat."]})
    tables, _ = make_operator(doc_content_column="body").transform(table)
    assert "docq_total_words" in tables[0].column_names


def test_transform_quality_values():
    """transform() produces sensible docq_ values: positive word count and nonzero lorem ratio for lorem text."""
    tables, _ = make_operator().transform(make_table(["lorem ipsum dolor sit amet"]))
    result = tables[0]
    assert result.column("docq_total_words")[0].as_py() > 0
    assert result.column("docq_lorem_ipsum_ratio")[0].as_py() > 0
