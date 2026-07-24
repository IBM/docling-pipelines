#!/usr/bin/env python3
"""
Unit tests for AbstractOperator base class.
Tests initialization, validation, metadata handling, and utility methods.
"""

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import (
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory

# ---------------------------------------------------------------------------
# Test Operator Implementation
# ---------------------------------------------------------------------------


class TestOperator(AbstractOperator):
    """Concrete test implementation of AbstractOperator for testing."""

    short_name = "test_operator"
    category = OperatorCategory.Functional

    def __init__(self, config: dict):
        super().__init__(config)
        self.required_features = config.get("required_features", [])

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict]:
        """Simple transform that returns input table unchanged."""
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)
        metadata[Metrics.External.PROCESSED_DOCS] = table.num_rows
        return [table], metadata

    def get_required_features(self):
        """Return configured required features."""
        return self.required_features


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_config(**kwargs) -> dict:
    """Create a test config dictionary with default values."""
    config = {
        OperatorConstants.Misc.NAME: "test_op",
        OperatorConstants.Misc.ID: "test_id_123",
        DocpipeConstants.JOB_ID: "job_001",
        DocpipeConstants.JOB_RUN_ID: "run_001",
    }
    config.update(kwargs)
    return config


def make_operator(config=None) -> TestOperator:
    """Create a TestOperator instance."""
    if config is None:
        config = make_config()
    return TestOperator(config)


def make_table(num_rows=3) -> pa.Table:
    """Create a simple test PyArrow table."""
    return pa.table(
        {
            "id": [str(i + 1) for i in range(num_rows)],
            "content": [f"Document {i + 1}" for i in range(num_rows)],
        }
    )


# ---------------------------------------------------------------------------
# 1. Constructor Initialization
# ---------------------------------------------------------------------------


def test_init_with_all_config_parameters():
    """Constructor initializes all config parameters correctly."""
    config = make_config(
        **{
            OperatorConstants.Misc.NAME: "my_operator",
            OperatorConstants.Misc.ID: "op_456",
            DocpipeConstants.JOB_ID: "job_999",
            DocpipeConstants.JOB_RUN_ID: "run_888",
            DocpipeConstants.CONTEXT_ID: "context_777",
            DocpipeConstants.OUTPUT_FEATURES_TO_DROP: ["feature1", "feature2"],
            DocpipeConstants.UPDATED_FEATURES: ["feature3"],
            DocpipeConstants.VALIDATING_FLOW: True,
        }
    )
    operator = make_operator(config)

    assert operator.name == "my_operator"
    assert operator.id == "op_456"
    assert operator.job_id == "job_999"
    assert operator.job_run_id == "run_888"
    assert operator.context_id == "context_777"
    assert operator.output_features_to_drop == ["feature1", "feature2"]
    assert operator.updated_features == ["feature3"]
    assert operator.validating_flow is True


def test_init_with_minimal_config():
    """Constructor works with minimal config (only required fields)."""
    config = {}
    operator = make_operator(config)

    assert operator.name is None
    assert operator.id is None
    assert operator.job_id is None
    assert operator.job_run_id is None


def test_init_context_id_defaults_to_job_id():
    """context_id defaults to job_id when not provided."""
    config = make_config()
    config.pop(DocpipeConstants.CONTEXT_ID, None)
    operator = make_operator(config)

    assert operator.context_id == operator.job_id


def test_init_context_id_uses_provided_value():
    """context_id uses provided value when specified."""
    config = make_config(**{DocpipeConstants.CONTEXT_ID: "custom_context"})
    operator = make_operator(config)

    assert operator.context_id == "custom_context"
    assert operator.context_id != operator.job_id


def test_init_output_features_to_drop_defaults_to_empty_list():
    """output_features_to_drop defaults to empty list."""
    config = make_config()
    operator = make_operator(config)

    assert operator.output_features_to_drop == []
    assert isinstance(operator.output_features_to_drop, list)


def test_init_updated_features_defaults_to_empty_list():
    """updated_features defaults to empty list."""
    config = make_config()
    operator = make_operator(config)

    assert operator.updated_features == []
    assert isinstance(operator.updated_features, list)


def test_init_validating_flow_defaults_to_false():
    """validating_flow defaults to False."""
    config = make_config()
    operator = make_operator(config)

    assert operator.validating_flow is False


def test_init_common_log_arguments_structure():
    """common_log_arguments contains job_id and job_run_id."""
    config = make_config()
    operator = make_operator(config)

    assert DocpipeConstants.JOB_ID in operator.common_log_arguments
    assert DocpipeConstants.JOB_RUN_ID in operator.common_log_arguments
    assert operator.common_log_arguments[DocpipeConstants.JOB_ID] == operator.job_id
    assert operator.common_log_arguments[DocpipeConstants.JOB_RUN_ID] == operator.job_run_id


# ---------------------------------------------------------------------------
# 2. is_available() Static Method
# ---------------------------------------------------------------------------


def test_is_available_returns_true():
    """is_available() returns True by default."""
    assert AbstractOperator.is_available() is True


def test_is_available_is_static_method():
    """is_available() can be called without instance."""
    result = AbstractOperator.is_available()
    assert result is True


def test_is_available_on_concrete_class():
    """is_available() works on concrete subclass."""
    assert TestOperator.is_available() is True


# ---------------------------------------------------------------------------
# 3. validate() Method
# ---------------------------------------------------------------------------


def test_validate_with_empty_errors_and_warnings():
    """validate() works with empty errors and warnings lists."""
    operator = make_operator()
    errors = []
    warnings = []
    available_features = ["feature1", "feature2"]

    operator.validate(errors, warnings, available_features)

    assert len(errors) == 0
    assert len(warnings) == 0


def test_validate_with_no_required_features():
    """validate() passes when operator has no required features."""
    config = make_config(required_features=[])
    operator = make_operator(config)
    errors = []
    warnings = []
    available_features = ["feature1"]

    operator.validate(errors, warnings, available_features)

    assert len(errors) == 0


def test_validate_with_all_required_features_present():
    """validate() passes when all required features are available."""
    config = make_config(required_features=["feature1", "feature2"])
    operator = make_operator(config)
    errors = []
    warnings = []
    available_features = ["feature1", "feature2", "feature3"]

    operator.validate(errors, warnings, available_features)

    assert len(errors) == 0


def test_validate_calls_operator_utils():
    """validate() delegates to OperatorUtils.validate_columns()."""
    config = make_config(required_features=["feature1"])
    operator = make_operator(config)
    errors = []
    warnings = []
    available_features = ["feature1"]

    # Should not raise when all required features are present
    operator.validate(errors, warnings, available_features)
    assert len(errors) == 0


# ---------------------------------------------------------------------------
# 4. get_required_features() Default Behavior
# ---------------------------------------------------------------------------


def test_get_required_features_default_returns_empty_list():
    """get_required_features() returns empty list by default."""
    operator = make_operator()
    result = operator.get_required_features()

    assert result == []
    assert isinstance(result, list)


def test_get_required_features_can_be_overridden():
    """get_required_features() can be overridden in subclass."""
    config = make_config(required_features=["custom_feature"])
    operator = make_operator(config)
    result = operator.get_required_features()

    assert result == ["custom_feature"]


# ---------------------------------------------------------------------------
# 5. get_metadata() Default Behavior
# ---------------------------------------------------------------------------


def test_get_metadata_default_returns_empty_dict():
    """get_metadata() returns empty dict by default."""
    operator = make_operator()
    result = operator.get_metadata()

    assert result == {}
    assert isinstance(result, dict)


def test_get_metadata_returns_dict_type():
    """get_metadata() always returns a dictionary."""
    operator = make_operator()
    result = operator.get_metadata()

    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 6. should_validate_field() Method
# ---------------------------------------------------------------------------


def test_should_validate_field_returns_true_when_not_validating_flow():
    """should_validate_field() returns True during execution phase."""
    config = make_config(**{DocpipeConstants.VALIDATING_FLOW: False})
    operator = make_operator(config)

    result = operator.should_validate_field(field_value="test")

    assert result is True


def test_should_validate_field_returns_false_when_validating_flow():
    """should_validate_field() returns False during validation phase."""
    config = make_config(**{DocpipeConstants.VALIDATING_FLOW: True})
    operator = make_operator(config)

    result = operator.should_validate_field(field_value="test")

    assert result is False


def test_should_validate_field_with_none_value_not_validating():
    """should_validate_field() returns True for None value when not validating."""
    config = make_config(**{DocpipeConstants.VALIDATING_FLOW: False})
    operator = make_operator(config)

    result = operator.should_validate_field(field_value=None)

    assert result is True


def test_should_validate_field_with_none_value_validating():
    """should_validate_field() returns False for None value when validating."""
    config = make_config(**{DocpipeConstants.VALIDATING_FLOW: True})
    operator = make_operator(config)

    result = operator.should_validate_field(field_value=None)

    assert result is False


def test_should_validate_field_with_empty_string():
    """should_validate_field() behavior with empty string value."""
    config = make_config(**{DocpipeConstants.VALIDATING_FLOW: False})
    operator = make_operator(config)

    result = operator.should_validate_field(field_value="")

    assert result is True


def test_should_validate_field_with_complex_value():
    """should_validate_field() behavior with complex value types."""
    config = make_config(**{DocpipeConstants.VALIDATING_FLOW: False})
    operator = make_operator(config)

    result = operator.should_validate_field(field_value={"key": "value"})

    assert result is True


# ---------------------------------------------------------------------------
# 7. create_base_metadata() Static Method
# ---------------------------------------------------------------------------


def test_create_base_metadata_with_default_status():
    """create_base_metadata() creates metadata with default COMPLETED status."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    assert metadata[Metrics.External.TOTAL_DOCS] == 10
    assert metadata[Metrics.External.PROCESSED_DOCS] == 0
    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0
    assert metadata[Metrics.External.FAILED_DOCS] == []
    assert metadata[Metrics.External.SKIPPED_DOCS_COUNT] == 0
    assert metadata[Metrics.External.SKIPPED_DOCS] == []
    assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value


def test_create_base_metadata_with_custom_status_enum():
    """create_base_metadata() accepts ExecutionStatus enum for node_status."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=5, node_status=ExecutionStatus.FAILED)

    assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.FAILED.value


def test_create_base_metadata_with_custom_status_string():
    """create_base_metadata() accepts string for node_status."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=5, node_status="CustomStatus")

    assert metadata[Metrics.External.NODE_STATUS] == "CustomStatus"


def test_create_base_metadata_with_zero_docs():
    """create_base_metadata() works with zero documents."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=0)

    assert metadata[Metrics.External.TOTAL_DOCS] == 0
    assert metadata[Metrics.External.PROCESSED_DOCS] == 0


def test_create_base_metadata_with_large_doc_count():
    """create_base_metadata() works with large document counts."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=1_000_000)

    assert metadata[Metrics.External.TOTAL_DOCS] == 1_000_000


def test_create_base_metadata_structure_completeness():
    """create_base_metadata() includes all required fields."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    required_fields = [
        Metrics.External.TOTAL_DOCS,
        Metrics.External.PROCESSED_DOCS,
        Metrics.External.FAILED_DOCS_COUNT,
        Metrics.External.FAILED_DOCS,
        Metrics.External.SKIPPED_DOCS_COUNT,
        Metrics.External.SKIPPED_DOCS,
        Metrics.External.NODE_STATUS,
    ]

    for field in required_fields:
        assert field in metadata, f"Missing required field: {field}"


def test_create_base_metadata_failed_docs_is_list():
    """create_base_metadata() initializes failed_docs as empty list."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    assert isinstance(metadata[Metrics.External.FAILED_DOCS], list)
    assert len(metadata[Metrics.External.FAILED_DOCS]) == 0


def test_create_base_metadata_skipped_docs_is_list():
    """create_base_metadata() initializes skipped_docs as empty list."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    assert isinstance(metadata[Metrics.External.SKIPPED_DOCS], list)
    assert len(metadata[Metrics.External.SKIPPED_DOCS]) == 0


# ---------------------------------------------------------------------------
# 8. record_failed_document() Static Method
# ---------------------------------------------------------------------------


def test_record_failed_document_increments_count():
    """record_failed_document() increments failed_docs_count."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)
    initial_count = metadata[Metrics.External.FAILED_DOCS_COUNT]

    AbstractOperator.record_failed_document(
        metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Test failure"
    )

    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == initial_count + 1


def test_record_failed_document_adds_to_list():
    """record_failed_document() adds document to failed_docs list."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_failed_document(
        metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Test failure"
    )

    assert len(metadata[Metrics.External.FAILED_DOCS]) == 1
    failed_doc = metadata[Metrics.External.FAILED_DOCS][0]
    assert failed_doc["id"] == "doc1"
    assert failed_doc["name"] == "Document 1"
    assert failed_doc["reason"] == "Test failure"
    assert failed_doc["document_url"] == ""


def test_record_failed_document_multiple_failures():
    """record_failed_document() handles multiple failed documents."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_failed_document(metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Reason 1")
    AbstractOperator.record_failed_document(metadata=metadata, doc_id="doc2", doc_name="Document 2", reason="Reason 2")
    AbstractOperator.record_failed_document(metadata=metadata, doc_id="doc3", doc_name="Document 3", reason="Reason 3")

    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 3
    assert len(metadata[Metrics.External.FAILED_DOCS]) == 3


def test_record_failed_document_with_empty_strings():
    """record_failed_document() handles empty string values."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_failed_document(metadata=metadata, doc_id="", doc_name="", reason="")

    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
    failed_doc = metadata[Metrics.External.FAILED_DOCS][0]
    assert failed_doc["id"] == ""
    assert failed_doc["name"] == ""
    assert failed_doc["reason"] == ""


def test_record_failed_document_with_special_characters():
    """record_failed_document() handles special characters in strings."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_failed_document(
        metadata=metadata,
        doc_id="doc-123_456",
        doc_name="Document: Test & Special <chars>",
        reason="Failed due to 'error' in processing",
    )

    failed_doc = metadata[Metrics.External.FAILED_DOCS][0]
    assert failed_doc["id"] == "doc-123_456"
    assert "Special <chars>" in failed_doc["name"]


def test_record_failed_document_preserves_existing_failures():
    """record_failed_document() preserves previously recorded failures."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_failed_document(metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Reason 1")
    first_doc = metadata[Metrics.External.FAILED_DOCS][0]

    AbstractOperator.record_failed_document(metadata=metadata, doc_id="doc2", doc_name="Document 2", reason="Reason 2")

    assert len(metadata[Metrics.External.FAILED_DOCS]) == 2
    assert metadata[Metrics.External.FAILED_DOCS][0] == first_doc


# ---------------------------------------------------------------------------
# 9. record_skipped_document() Static Method
# ---------------------------------------------------------------------------


def test_record_skipped_document_increments_count():
    """record_skipped_document() increments skipped_docs_count."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)
    initial_count = metadata[Metrics.External.SKIPPED_DOCS_COUNT]

    AbstractOperator.record_skipped_document(
        metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Test skip"
    )

    assert metadata[Metrics.External.SKIPPED_DOCS_COUNT] == initial_count + 1


def test_record_skipped_document_adds_to_list():
    """record_skipped_document() adds document to skipped_docs list."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_skipped_document(
        metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Test skip"
    )

    assert len(metadata[Metrics.External.SKIPPED_DOCS]) == 1
    skipped_doc = metadata[Metrics.External.SKIPPED_DOCS][0]
    assert skipped_doc["id"] == "doc1"
    assert skipped_doc["name"] == "Document 1"
    assert skipped_doc["reason"] == "Test skip"
    assert skipped_doc["document_url"] == ""


def test_record_skipped_document_multiple_skips():
    """record_skipped_document() handles multiple skipped documents."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_skipped_document(metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Reason 1")
    AbstractOperator.record_skipped_document(metadata=metadata, doc_id="doc2", doc_name="Document 2", reason="Reason 2")

    assert metadata[Metrics.External.SKIPPED_DOCS_COUNT] == 2
    assert len(metadata[Metrics.External.SKIPPED_DOCS]) == 2


def test_record_skipped_document_with_empty_strings():
    """record_skipped_document() handles empty string values."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_skipped_document(metadata=metadata, doc_id="", doc_name="", reason="")

    assert metadata[Metrics.External.SKIPPED_DOCS_COUNT] == 1
    skipped_doc = metadata[Metrics.External.SKIPPED_DOCS][0]
    assert skipped_doc["id"] == ""
    assert skipped_doc["name"] == ""
    assert skipped_doc["reason"] == ""


def test_record_skipped_document_preserves_existing_skips():
    """record_skipped_document() preserves previously recorded skips."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_skipped_document(metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Reason 1")
    first_doc = metadata[Metrics.External.SKIPPED_DOCS][0]

    AbstractOperator.record_skipped_document(metadata=metadata, doc_id="doc2", doc_name="Document 2", reason="Reason 2")

    assert len(metadata[Metrics.External.SKIPPED_DOCS]) == 2
    assert metadata[Metrics.External.SKIPPED_DOCS][0] == first_doc


# ---------------------------------------------------------------------------
# 10. Metadata Integration - Failed and Skipped Together
# ---------------------------------------------------------------------------


def test_metadata_tracks_both_failed_and_skipped():
    """Metadata can track both failed and skipped documents simultaneously."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_failed_document(metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Failed")
    AbstractOperator.record_skipped_document(metadata=metadata, doc_id="doc2", doc_name="Document 2", reason="Skipped")

    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
    assert metadata[Metrics.External.SKIPPED_DOCS_COUNT] == 1
    assert len(metadata[Metrics.External.FAILED_DOCS]) == 1
    assert len(metadata[Metrics.External.SKIPPED_DOCS]) == 1


def test_metadata_failed_and_skipped_are_independent():
    """Failed and skipped document lists are independent."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_failed_document(metadata=metadata, doc_id="doc1", doc_name="Document 1", reason="Failed")
    AbstractOperator.record_skipped_document(metadata=metadata, doc_id="doc2", doc_name="Document 2", reason="Skipped")

    failed_doc = metadata[Metrics.External.FAILED_DOCS][0]
    skipped_doc = metadata[Metrics.External.SKIPPED_DOCS][0]

    assert failed_doc["id"] != skipped_doc["id"]
    assert failed_doc["reason"] == "Failed"
    assert skipped_doc["reason"] == "Skipped"


# ---------------------------------------------------------------------------
# 11. Class Attributes
# ---------------------------------------------------------------------------


def test_operator_category_enum_values():
    """OperatorCategory enum has expected values."""
    assert OperatorCategory.Extract == "Extract"
    assert OperatorCategory.Ingest == "Ingest"
    assert OperatorCategory.Functional == "Functional"
    assert OperatorCategory.Quality == "Quality"
    assert OperatorCategory.VectorDB == "VectorDB"
    assert OperatorCategory.Storage == "Storage"


def test_concrete_operator_can_set_short_name():
    """Concrete operator can set short_name."""
    assert TestOperator.short_name == "test_operator"


def test_concrete_operator_can_set_category():
    """Concrete operator can set category."""
    assert TestOperator.category == OperatorCategory.Functional


# ---------------------------------------------------------------------------
# 12. Edge Cases
# ---------------------------------------------------------------------------


def test_init_with_none_values_in_config():
    """Constructor handles None values in config."""
    config = {
        OperatorConstants.Misc.NAME: None,
        OperatorConstants.Misc.ID: None,
        DocpipeConstants.JOB_ID: None,
        DocpipeConstants.JOB_RUN_ID: None,
    }
    operator = make_operator(config)

    assert operator.name is None
    assert operator.id is None
    assert operator.job_id is None
    assert operator.job_run_id is None


def test_validate_with_none_in_available_features():
    """validate() handles None values in available_features list."""
    config = make_config(required_features=["feature1"])
    operator = make_operator(config)
    errors = []
    warnings = []
    available_features = ["feature1", None, "feature2"]

    operator.validate(errors, warnings, available_features)

    # Should not raise an error since feature1 is present
    assert len(errors) == 0


def test_create_base_metadata_with_negative_doc_count():
    """create_base_metadata() handles negative document count."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=-1)

    assert metadata[Metrics.External.TOTAL_DOCS] == -1


def test_record_failed_document_with_long_reason():
    """record_failed_document() handles very long reason strings."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)
    long_reason = "A" * 10000

    AbstractOperator.record_failed_document(metadata=metadata, doc_id="doc1", doc_name="Document 1", reason=long_reason)

    failed_doc = metadata[Metrics.External.FAILED_DOCS][0]
    assert len(failed_doc["reason"]) == 10000


def test_record_skipped_document_with_unicode_characters():
    """record_skipped_document() handles Unicode characters."""
    metadata = AbstractOperator.create_base_metadata(total_docs_count=10)

    AbstractOperator.record_skipped_document(
        metadata=metadata,
        doc_id="doc_日本語",
        doc_name="文書 テスト",
        reason="スキップされました",
    )

    skipped_doc = metadata[Metrics.External.SKIPPED_DOCS][0]
    assert skipped_doc["id"] == "doc_日本語"
    assert skipped_doc["name"] == "文書 テスト"
    assert skipped_doc["reason"] == "スキップされました"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
