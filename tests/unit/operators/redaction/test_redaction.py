import pyarrow as pa

from core.operators.quality.redaction import RedactionOperator
from common.constants.operator_constants import OperatorConstants
from common.constants.constants import Metrics


class TestRedactionOperator:
    """Test cases for RedactionOperator"""

    def test_redaction_with_simple_word(self):
        """Test redacting a simple word"""
        config = {
            "doc_column": "content",
            "stats_column": "redaction_stats",
            "redaction_masking_character": "X",
            "redaction_regex": "John",
        }
        operator = RedactionOperator(config=config)

        content = pa.array(
            ["John Doe is here", "Mary Smith is there", "John and John again"]
        )
        names = pa.array(["doc1", "doc2", "doc3"])
        ids = pa.array([1, 2, 3])
        input_table = pa.Table.from_arrays(
            [ids, names, content], names=["id", "name", "content"]
        )

        table_list, metadata = operator.transform(input_table)

        assert len(table_list) == 1
        output_table = table_list[0]

        # Check redacted content
        redacted_content = output_table["content"].to_pylist()
        assert redacted_content[0] == "XXXX Doe is here"
        assert redacted_content[1] == "Mary Smith is there"  # No match
        assert redacted_content[2] == "XXXX and XXXX again"

        # Check redaction stats
        stats = output_table["redaction_stats"].to_pylist()
        assert stats[0] == 1
        assert stats[1] == 0
        assert stats[2] == 2

        # Check metadata
        assert (
            metadata[Metrics.External.PROCESSED_DOCS] == 2
        )  # Only docs with redactions
        assert metadata["total_redactions"] == 3

    def test_redaction_with_regex_pattern(self):
        """Test redacting with a regex pattern (SSN)"""
        config = {
            "doc_column": "content",
            "stats_column": "redaction_stats",
            "redaction_masking_character": "*",
            "redaction_regex": r"\d{3}-\d{2}-\d{4}",
        }
        operator = RedactionOperator(config=config)

        content = pa.array(
            ["SSN: 123-45-6789", "No SSN here", "Multiple: 111-22-3333 and 444-55-6666"]
        )
        names = pa.array(["doc1", "doc2", "doc3"])
        ids = pa.array([1, 2, 3])
        input_table = pa.Table.from_arrays(
            [ids, names, content], names=["id", "name", "content"]
        )

        table_list, _ = operator.transform(input_table)

        output_table = table_list[0]
        redacted_content = output_table["content"].to_pylist()

        assert redacted_content[0] == "SSN: ***********"
        assert redacted_content[1] == "No SSN here"
        assert redacted_content[2] == "Multiple: *********** and ***********"

        stats = output_table["redaction_stats"].to_pylist()
        assert stats[0] == 1
        assert stats[1] == 0
        assert stats[2] == 2

    def test_redaction_with_no_pattern(self):
        """Test operator behavior when no pattern is provided"""
        config = {"doc_column": "content", "stats_column": "redaction_stats"}
        operator = RedactionOperator(config=config)

        content = pa.array(["Some content"])
        names = pa.array(["doc1"])
        ids = pa.array([1])
        input_table = pa.Table.from_arrays(
            [ids, names, content], names=["id", "name", "content"]
        )

        table_list, metadata = operator.transform(input_table)

        # Should return original table unchanged
        assert len(table_list) == 1
        assert table_list[0] == input_table
        assert metadata[Metrics.External.NODE_STATUS] == "CompletedWithWarnings"

    def test_redaction_with_custom_masking_character(self):
        """Test redaction with custom masking character"""
        config = {
            "doc_column": "content",
            "stats_column": "redaction_stats",
            "redaction_masking_character": "#",
            "redaction_regex": "secret",
        }
        operator = RedactionOperator(config=config)

        content = pa.array(["This is a secret message"])
        names = pa.array(["doc1"])
        ids = pa.array([1])
        input_table = pa.Table.from_arrays(
            [ids, names, content], names=["id", "name", "content"]
        )

        table_list, metadata = operator.transform(input_table)

        output_table = table_list[0]
        redacted_content = output_table["content"].to_pylist()
        assert redacted_content[0] == "This is a ###### message"

    def test_get_metadata(self):
        """Test get_metadata returns correct structure"""
        config = {"doc_column": "content", "redaction_regex": "test"}
        operator = RedactionOperator(config=config)
        metadata = operator.get_metadata()

        assert OperatorConstants.Misc.CATEGORY in metadata
        assert OperatorConstants.Misc.LABEL in metadata
        assert metadata[OperatorConstants.Misc.LABEL] == "Redaction"
        assert OperatorConstants.Config.FEATURES in metadata
        assert OperatorConstants.Config.ATTRIBUTES in metadata

    def test_get_required_features(self):
        """Test get_required_features returns doc_column"""
        config = {"doc_column": "my_content", "redaction_regex": "test"}
        operator = RedactionOperator(config=config)
        required = operator.get_required_features()

        assert required == ["my_content"]

    def test_validate_with_empty_pattern(self):
        """Test validation warns when pattern is empty"""
        config = {"doc_column": "content", "redaction_regex": ""}
        operator = RedactionOperator(config=config)

        errors = []
        warnings = []
        available_features = ["content"]

        operator.validate(errors, warnings, available_features)

        assert len(warnings) == 1
        assert "empty" in warnings[0].lower()
