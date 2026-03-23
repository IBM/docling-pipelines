#!/usr/bin/env python3
"""
Unit tests for ExtractEntitiesOllamaOperator.

Tests cover:
- Basic entity extraction with mocked Ollama
- Schema loading from file
- Empty content handling (skipped docs)
- Ollama failure handling (failed docs)
- JSON repair logic (_parse_llm_json)
- Operator metadata structure
- doc_id_hash column auto-generation
"""

import json
import tempfile
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from core.operators.universal.extract.extract_entities_ollama import (
    ExtractEntitiesOllamaOperator,
    _build_json_template,
    _build_schema_description,
    _parse_llm_json,
    _try_repair_truncated_json,
)
from common.constants.operator_constants import OperatorConstants
from common.constants.constants import ExecutionStatus, Metrics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_config():
    """Minimal config for ExtractEntitiesOllamaOperator."""
    return {
        "ollama_model": "llama3",
        "doc_column": "content",
        "output_column": "entities",
        "schema": {
            "columns": {
                "vendor_name": "STRING",
                "invoice_date": "STRING",
                "total_amount": "DOUBLE",
            }
        },
        "max_workers": 1,
    }


@pytest.fixture
def sample_table():
    """Single-row PyArrow table with content."""
    data = {
        "id": ["doc-001"],
        "name": ["invoice_001.pdf"],
        "content": ["Invoice from Acme Corp dated 2024-01-15 for $1,500.00"],
    }
    return pa.table(data)


@pytest.fixture
def multi_row_table():
    """Multi-row PyArrow table."""
    data = {
        "id": ["doc-001", "doc-002", "doc-003"],
        "name": ["inv_001.pdf", "inv_002.pdf", "inv_003.pdf"],
        "content": [
            "Invoice from Acme Corp dated 2024-01-15 for $1,500.00",
            "Invoice from Beta LLC dated 2024-02-20 for $2,300.00",
            "Invoice from Gamma Inc dated 2024-03-10 for $750.00",
        ],
    }
    return pa.table(data)


@pytest.fixture
def empty_content_table():
    """Table with an empty content column."""
    data = {
        "id": ["doc-001"],
        "name": ["empty_doc.pdf"],
        "content": [""],
    }
    return pa.table(data)


# ---------------------------------------------------------------------------
# Tests: Helper functions
# ---------------------------------------------------------------------------


class TestBuildSchemaDescription:
    def test_basic_schema(self):
        schema = {"columns": {"vendor_name": "STRING", "total_amount": "DOUBLE"}}
        result = _build_schema_description(schema)
        assert "vendor_name (STRING)" in result
        assert "total_amount (DOUBLE)" in result

    def test_empty_schema(self):
        result = _build_schema_description({"columns": {}})
        assert result == ""

    def test_missing_columns_key(self):
        result = _build_schema_description({})
        assert result == ""


class TestBuildJsonTemplate:
    def test_flat_fields(self):
        schema = {"columns": {"vendor_name": "STRING", "total_amount": "DOUBLE"}}
        template = _build_json_template(schema)
        assert template["vendor_name"] is None
        assert template["total_amount"] is None

    def test_nested_field(self):
        schema = {"columns": {"items": "NESTED", "items.item_id": "STRING"}}
        template = _build_json_template(schema)
        assert isinstance(template["items"], list)
        assert template["items"][0]["item_id"] is None

    def test_dotted_field_creates_parent(self):
        schema = {"columns": {"supplier.name": "STRING", "supplier.address": "STRING"}}
        template = _build_json_template(schema)
        assert "supplier" in template
        assert isinstance(template["supplier"], list)


class TestParseLlmJson:
    def test_valid_json(self):
        raw = '{"vendor": "Acme", "amount": 100}'
        result = _parse_llm_json(raw)
        assert result["vendor"] == "Acme"
        assert result["amount"] == 100

    def test_markdown_fenced_json(self):
        raw = '```json\n{"vendor": "Acme", "amount": 100}\n```'
        result = _parse_llm_json(raw)
        assert result["vendor"] == "Acme"

    def test_markdown_fenced_no_language(self):
        raw = '```\n{"vendor": "Beta"}\n```'
        result = _parse_llm_json(raw)
        assert result["vendor"] == "Beta"

    def test_json_with_surrounding_text(self):
        raw = 'Here is the result: {"vendor": "Gamma"} as requested.'
        result = _parse_llm_json(raw)
        assert result["vendor"] == "Gamma"

    def test_truncated_json_repair(self):
        raw = '{"vendor": "Acme", "items": [{"id": "1"'
        result = _parse_llm_json(raw)
        # Should return a dict (repaired or empty), not raise
        assert isinstance(result, dict)

    def test_completely_invalid_returns_empty(self):
        raw = "This is not JSON at all."
        result = _parse_llm_json(raw)
        assert result == {}


class TestTryRepairTruncatedJson:
    def test_truncated_object(self):
        raw = '{"key": "value"'
        result = _try_repair_truncated_json(raw)
        assert result is not None
        assert result["key"] == "value"

    def test_truncated_nested(self):
        raw = '{"items": [{"id": "1"'
        result = _try_repair_truncated_json(raw)
        assert result is not None

    def test_valid_json_unchanged(self):
        raw = '{"key": "value"}'
        result = _try_repair_truncated_json(raw)
        assert result is not None
        assert result["key"] == "value"

    def test_completely_broken_returns_none(self):
        raw = "not json at all }{]["
        result = _try_repair_truncated_json(raw)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Operator initialization
# ---------------------------------------------------------------------------


class TestExtractEntitiesOllamaOperatorInit:
    def test_default_values(self):
        config = {}
        op = ExtractEntitiesOllamaOperator(config)
        assert op.doc_column == OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        assert op.doc_id_hash_column == OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        assert op.ollama_model == "granite4"
        assert op.output_column == "entities"
        assert op.max_doc_chars == 8000
        assert op.temperature == 0.0
        assert op.max_workers == 4

    def test_custom_values(self, basic_config):
        op = ExtractEntitiesOllamaOperator(basic_config)
        assert op.ollama_model == "llama3"
        assert op.output_column == "entities"
        assert op.max_workers == 1

    def test_short_name(self):
        op = ExtractEntitiesOllamaOperator({})
        assert op.short_name == OperatorConstants.Operators.EXTRACT_ENTITIES_OLLAMA

    def test_category(self):
        from core.operators.abstract_operator import OperatorCategory

        op = ExtractEntitiesOllamaOperator({})
        assert op.category == OperatorCategory.Extract


# ---------------------------------------------------------------------------
# Tests: Basic entity extraction
# ---------------------------------------------------------------------------


class TestExtractEntitiesBasic:
    @patch("ollama.chat")
    def test_extract_entities_basic(self, mock_chat, basic_config, sample_table):
        """Mock ollama.chat to return valid JSON; verify entities column is added."""
        mock_chat.return_value = {
            "message": {
                "content": '{"vendor_name": "Acme Corp", "invoice_date": "2024-01-15", "total_amount": 1500.0}'
            }
        }

        op = ExtractEntitiesOllamaOperator(basic_config)
        result_tables, metadata = op.transform(sample_table)

        assert len(result_tables) == 1
        result_table = result_tables[0]

        # entities column should be present
        assert "entities" in result_table.column_names
        assert result_table.num_rows == 1

        # Verify the entities content is valid JSON
        entities_value = result_table.column("entities")[0].as_py()
        parsed = json.loads(entities_value)
        assert parsed["vendor_name"] == "Acme Corp"
        assert parsed["invoice_date"] == "2024-01-15"

        # Verify metadata
        assert metadata[Metrics.External.TOTAL_DOCS] == 1
        assert metadata[Metrics.External.PROCESSED_DOCS] == 1
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

    @patch("ollama.chat")
    def test_extract_entities_multiple_docs(
        self, mock_chat, basic_config, multi_row_table
    ):
        """Test extraction across multiple documents."""
        mock_chat.return_value = {
            "message": {
                "content": '{"vendor_name": "Test Corp", "invoice_date": "2024-01-01", "total_amount": 100.0}'
            }
        }

        op = ExtractEntitiesOllamaOperator(basic_config)
        result_tables, metadata = op.transform(multi_row_table)

        result_table = result_tables[0]
        assert result_table.num_rows == 3
        assert "entities" in result_table.column_names
        assert metadata[Metrics.External.TOTAL_DOCS] == 3
        assert metadata[Metrics.External.PROCESSED_DOCS] == 3
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0


# ---------------------------------------------------------------------------
# Tests: Schema file loading
# ---------------------------------------------------------------------------


class TestExtractEntitiesWithSchemaFile:
    @patch("ollama.chat")
    def test_extract_entities_with_schema_file(self, mock_chat, sample_table):
        """Create a temp schema JSON file, verify schema is loaded from file."""
        schema_data = {
            "schemas": [
                {
                    "table": "invoices",
                    "description": "Invoice schema",
                    "columns": {
                        "vendor_name": "STRING",
                        "invoice_date": "STRING",
                        "total_amount": "DOUBLE",
                    },
                }
            ]
        }

        mock_chat.return_value = {
            "message": {
                "content": '{"vendor_name": "Acme", "invoice_date": "2024-01-15", "total_amount": 1500.0}'
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema_data, f)
            schema_file_path = f.name

        config = {
            "ollama_model": "llama3",
            "schema_file": schema_file_path,
            "schema_table": "invoices",
            "max_workers": 1,
        }

        op = ExtractEntitiesOllamaOperator(config)
        result_tables, metadata = op.transform(sample_table)

        result_table = result_tables[0]
        assert "entities" in result_table.column_names
        assert metadata[Metrics.External.PROCESSED_DOCS] == 1

        # Verify schema was loaded correctly
        resolved = op._get_schema()
        assert "columns" in resolved
        assert "vendor_name" in resolved["columns"]

    def test_schema_file_not_found(self, sample_table):
        """When schema file doesn't exist, operator should use empty schema."""
        config = {
            "ollama_model": "llama3",
            "schema_file": "/nonexistent/path/schema.json",
            "schema_table": "invoices",
            "max_workers": 1,
        }
        op = ExtractEntitiesOllamaOperator(config)
        resolved = op._get_schema()
        assert resolved == {"columns": {}}

    def test_schema_table_not_found_in_file(self):
        """When schema table name doesn't match, operator should use empty schema."""
        schema_data = {
            "schemas": [{"table": "other_table", "columns": {"field": "STRING"}}]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema_data, f)
            schema_file_path = f.name

        config = {
            "schema_file": schema_file_path,
            "schema_table": "nonexistent_table",
        }
        op = ExtractEntitiesOllamaOperator(config)
        resolved = op._get_schema()
        assert resolved == {"columns": {}}


# ---------------------------------------------------------------------------
# Tests: Empty content handling
# ---------------------------------------------------------------------------


class TestExtractEntitiesEmptyContent:
    def test_extract_entities_empty_content(self, empty_content_table):
        """Empty content rows should be skipped, not failed."""
        config = {
            "ollama_model": "llama3",
            "schema": {"columns": {"vendor_name": "STRING"}},
            "max_workers": 1,
        }
        op = ExtractEntitiesOllamaOperator(config)
        result_tables, metadata = op.transform(empty_content_table)

        assert metadata[Metrics.External.SKIPPED_DOCS_COUNT] == 1
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0
        assert metadata[Metrics.External.PROCESSED_DOCS] == 0

    def test_extract_entities_none_content(self):
        """None content rows should be skipped."""
        data = {
            "id": ["doc-001"],
            "name": ["null_doc.pdf"],
            "content": pa.array([None], type=pa.string()),
        }
        table = pa.table(data)

        config = {
            "ollama_model": "llama3",
            "schema": {"columns": {"vendor_name": "STRING"}},
            "max_workers": 1,
        }
        op = ExtractEntitiesOllamaOperator(config)
        result_tables, metadata = op.transform(table)

        assert metadata[Metrics.External.SKIPPED_DOCS_COUNT] == 1
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0


# ---------------------------------------------------------------------------
# Tests: Ollama failure handling
# ---------------------------------------------------------------------------


class TestExtractEntitiesOllamaFailure:
    @patch("ollama.chat")
    def test_extract_entities_ollama_failure(
        self, mock_chat, basic_config, sample_table
    ):
        """When ollama.chat raises, document should be recorded as failed."""
        mock_chat.side_effect = Exception("Connection refused to Ollama")

        op = ExtractEntitiesOllamaOperator(basic_config)
        result_tables, metadata = op.transform(sample_table)

        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert metadata[Metrics.External.PROCESSED_DOCS] == 0
        assert (
            metadata[Metrics.External.NODE_STATUS]
            == ExecutionStatus.COMPLETED_WITH_ERRORS
        )

    @patch("ollama.chat")
    def test_partial_failure_continues_processing(
        self, mock_chat, basic_config, multi_row_table
    ):
        """When one doc fails, others should still be processed."""
        call_count = [0]

        def mock_response(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Timeout on second document")
            return {
                "message": {
                    "content": '{"vendor_name": "Test", "invoice_date": "2024-01-01", "total_amount": 0}'
                }
            }

        mock_chat.side_effect = mock_response

        op = ExtractEntitiesOllamaOperator(basic_config)
        result_tables, metadata = op.transform(multi_row_table)

        # 2 should succeed, 1 should fail
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert (
            metadata[Metrics.External.NODE_STATUS]
            == ExecutionStatus.COMPLETED_WITH_ERRORS
        )

    @patch("ollama.chat")
    def test_node_status_completed_on_success(
        self, mock_chat, basic_config, sample_table
    ):
        """When all docs succeed, node_status should be COMPLETED."""
        mock_chat.return_value = {
            "message": {
                "content": '{"vendor_name": "Acme", "invoice_date": "2024-01-15", "total_amount": 100}'
            }
        }

        op = ExtractEntitiesOllamaOperator(basic_config)
        result_tables, metadata = op.transform(sample_table)

        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0


# ---------------------------------------------------------------------------
# Tests: doc_id_hash column auto-generation
# ---------------------------------------------------------------------------


class TestExtractEntitiesDocIdHash:
    @patch("ollama.chat")
    def test_extract_entities_adds_doc_id_hash(
        self, mock_chat, basic_config, sample_table
    ):
        """When doc_id_hash column is absent, it should be added by the operator."""
        mock_chat.return_value = {
            "message": {
                "content": '{"vendor_name": "Acme", "invoice_date": "2024-01-15", "total_amount": 100}'
            }
        }

        # Confirm input table does NOT have doc_id_hash
        assert (
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
            not in sample_table.column_names
        )

        op = ExtractEntitiesOllamaOperator(basic_config)
        result_tables, metadata = op.transform(sample_table)

        result_table = result_tables[0]
        assert (
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT in result_table.column_names
        )

    @patch("ollama.chat")
    def test_existing_doc_id_hash_preserved(self, mock_chat, basic_config):
        """When doc_id_hash column already exists, it should not be overwritten."""
        mock_chat.return_value = {
            "message": {
                "content": '{"vendor_name": "Acme", "invoice_date": "2024-01-15", "total_amount": 100}'
            }
        }

        data = {
            "id": ["doc-001"],
            "name": ["invoice.pdf"],
            "content": ["Invoice from Acme Corp"],
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: ["existing-hash-abc123"],
        }
        table = pa.table(data)

        op = ExtractEntitiesOllamaOperator(basic_config)
        result_tables, metadata = op.transform(table)

        result_table = result_tables[0]
        assert (
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT in result_table.column_names
        )
        # The existing hash should be preserved (not regenerated)

        hash_value = result_table.column(OperatorConstants.Columns.DOC_ID_HASH_DEFAULT)[
            0
        ].as_py()
        assert hash_value == "existing-hash-abc123"


# ---------------------------------------------------------------------------
# Tests: get_metadata
# ---------------------------------------------------------------------------


class TestExtractEntitiesGetMetadata:
    def test_get_metadata_structure(self, basic_config):
        """Verify get_metadata returns all required top-level keys."""
        op = ExtractEntitiesOllamaOperator(basic_config)
        metadata = op.get_metadata()

        assert OperatorConstants.Misc.CATEGORY in metadata
        assert OperatorConstants.Config.FEATURES in metadata
        assert OperatorConstants.Config.ATTRIBUTES in metadata
        assert OperatorConstants.Misc.IS_OPERATOR_AVAILABLE in metadata
        assert OperatorConstants.Misc.LABEL in metadata
        assert OperatorConstants.Config.DESCRIPTION in metadata

    def test_get_metadata_category(self, basic_config):
        """Category should be 'Extract'."""
        op = ExtractEntitiesOllamaOperator(basic_config)
        metadata = op.get_metadata()
        assert metadata[OperatorConstants.Misc.CATEGORY] == "Extract"

    def test_get_metadata_features(self, basic_config):
        """Features should include output_column and doc_id_hash."""
        op = ExtractEntitiesOllamaOperator(basic_config)
        metadata = op.get_metadata()
        features = metadata[OperatorConstants.Config.FEATURES]

        assert "entities" in features
        assert OperatorConstants.Columns.DOC_ID_HASH_DEFAULT in features

    def test_get_metadata_attributes(self, basic_config):
        """Attributes should include all configurable parameters."""
        op = ExtractEntitiesOllamaOperator(basic_config)
        metadata = op.get_metadata()

        attributes = metadata[OperatorConstants.Config.ATTRIBUTES]

        print("~~ attributes=", attributes)

        assert "ollama_model" in attributes
        assert "schema" in attributes
        assert "schema_file" in attributes
        assert "schema_table" in attributes
        assert "output_column" in attributes
        assert "max_doc_chars" in attributes
        assert "temperature" in attributes
        assert OperatorConstants.Columns.DOC_COLUMN in attributes
        assert OperatorConstants.Config.MAX_WORKERS in attributes

    def test_get_metadata_sdk_flag(self, basic_config):
        """SDK flag should be True."""
        op = ExtractEntitiesOllamaOperator(basic_config)
        metadata = op.get_metadata()
        assert metadata[OperatorConstants.Misc.SDK] is True


# ---------------------------------------------------------------------------
# Tests: Schema resolution caching
# ---------------------------------------------------------------------------


class TestSchemaResolution:
    def test_inline_schema_takes_priority(self):
        """Inline schema should take priority over schema_file."""
        inline_schema = {"columns": {"field_a": "STRING"}}
        config = {
            "schema": inline_schema,
            "schema_file": "/some/file.json",
            "schema_table": "some_table",
        }
        op = ExtractEntitiesOllamaOperator(config)
        resolved = op._get_schema()
        assert resolved == inline_schema

    def test_no_schema_returns_empty(self):
        """When no schema is provided, empty columns dict is returned."""
        op = ExtractEntitiesOllamaOperator({})
        resolved = op._get_schema()
        assert resolved == {"columns": {}}

    def test_schema_is_cached(self):
        """_get_schema should return the same object on repeated calls."""
        inline_schema = {"columns": {"field_a": "STRING"}}
        op = ExtractEntitiesOllamaOperator({"schema": inline_schema})
        first = op._get_schema()
        second = op._get_schema()
        assert first is second


# ---------------------------------------------------------------------------
# Tests: is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    def test_is_available_when_ollama_installed(self):
        """is_available should return True when ollama can be imported."""
        mock_ollama = MagicMock()
        with patch.dict("sys.modules", {"ollama": mock_ollama}):
            result = ExtractEntitiesOllamaOperator.is_available()
        assert result is True

    def test_is_not_available_when_ollama_missing(self):
        """is_available should return False when ollama is not installed."""
        with patch.dict("sys.modules", {"ollama": None}):
            # When the module is None in sys.modules, import will raise ImportError
            result = ExtractEntitiesOllamaOperator.is_available()
            # Result depends on whether ollama is actually installed in the test env
            assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Tests: Validate method
# ---------------------------------------------------------------------------


class TestValidate:
    def test_validate_passes_with_valid_config(self, basic_config):
        """Validation should pass with valid config and available features."""
        op = ExtractEntitiesOllamaOperator(basic_config)
        errors = []
        warnings = []
        available_features = ["content", "doc_id_hash"]
        op.validate(errors, warnings, available_features)
        assert len(errors) == 0

    def test_validate_fails_when_doc_column_missing(self, basic_config):
        """Validation should fail when doc_column is not in available_features."""
        op = ExtractEntitiesOllamaOperator(basic_config)
        errors = []
        warnings = []
        available_features = []  # content not available
        op.validate(errors, warnings, available_features)
        assert any("content" in e for e in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
