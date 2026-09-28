"""Unit tests for AST static validation of custom operators."""

from pathlib import Path

import pytest

from docpipe.core.custom_operators.validation import validate_operator_file
from docpipe.exceptions.docpipe_exceptions import CustomOperatorInvalidDataException


class TestASTOperatorValidatorHappyPath:
    """Test suite for valid custom operator AST validation."""

    def test_validate_valid_operator_with_enum_category(self, *, tmp_path: Path) -> None:
        """Test validating a fully compliant custom operator with OperatorCategory enum."""
        code = """
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
import pyarrow as pa

class ValidCustomOp(AbstractOperator):
    short_name = "valid_custom_op"
    category = OperatorCategory.Quality
    owner = "custom"

    def transform(self, table: pa.Table):
        return [table], {}

    @staticmethod
    def get_metadata():
        return {"short_name": "valid_custom_op"}
"""
        op_file = tmp_path / "valid_op.py"
        op_file.write_text(code, encoding="utf-8")

        info = validate_operator_file(operator_file_path=op_file)
        assert info["short_name"] == "valid_custom_op"
        assert info["category"] == "Quality"
        assert info["class_name"] == "ValidCustomOp"

    def test_validate_valid_operator_with_string_category_and_owner_constant(self, *, tmp_path: Path) -> None:
        """Test category and owner specified as string literals."""
        code = """
from docpipe.core.operators.abstract_operator import AbstractOperator

class AnotherOp(AbstractOperator):
    short_name = "another_op"
    category = "Extract"
    owner = "custom"

    def transform(self, table):
        return [table], {}

    @staticmethod
    def get_metadata():
        return {}
"""
        op_file = tmp_path / "another_op.py"
        op_file.write_text(code, encoding="utf-8")

        info = validate_operator_file(operator_file_path=op_file)
        assert info["short_name"] == "another_op"
        assert info["category"] == "Extract"


class TestASTOperatorValidatorFailureCases:
    """Test suite for AST validation rejection rules."""

    def test_validate_syntax_error_raises_exception(self, *, tmp_path: Path) -> None:
        """Test reporting syntax error in operator file."""
        op_file = tmp_path / "syntax_err.py"
        op_file.write_text("def invalid syntax (", encoding="utf-8")

        with pytest.raises(CustomOperatorInvalidDataException, match="Syntax error"):
            validate_operator_file(operator_file_path=op_file)

    def test_validate_missing_file_raises_exception(self, *, tmp_path: Path) -> None:
        """Test validating non-existent file."""
        op_file = tmp_path / "non_existent.py"
        with pytest.raises(CustomOperatorInvalidDataException, match="Operator file does not exist"):
            validate_operator_file(operator_file_path=op_file)

    def test_validate_no_abstract_operator_subclass_raises_exception(self, *, tmp_path: Path) -> None:
        """Test rejection when no AbstractOperator subclass exists."""
        code = """
class RegularClass:
    short_name = "test"
"""
        op_file = tmp_path / "no_op.py"
        op_file.write_text(code, encoding="utf-8")

        with pytest.raises(CustomOperatorInvalidDataException, match="No class inheriting from AbstractOperator found"):
            validate_operator_file(operator_file_path=op_file)

    def test_validate_multiple_operator_classes_raises_exception(self, *, tmp_path: Path) -> None:
        """Test rejection when multiple AbstractOperator subclasses exist."""
        code = """
from docpipe.core.operators.abstract_operator import AbstractOperator

class Op1(AbstractOperator):
    short_name = "op1"
    category = "Extract"
    owner = "custom"
    def transform(self, table): pass
    @staticmethod
    def get_metadata(): pass

class Op2(AbstractOperator):
    short_name = "op2"
    category = "Extract"
    owner = "custom"
    def transform(self, table): pass
    @staticmethod
    def get_metadata(): pass
"""
        op_file = tmp_path / "multi_op.py"
        op_file.write_text(code, encoding="utf-8")

        with pytest.raises(CustomOperatorInvalidDataException, match="Multiple operator classes found"):
            validate_operator_file(operator_file_path=op_file)

    def test_validate_missing_short_name_raises_exception(self, *, tmp_path: Path) -> None:
        """Test rejection when short_name is missing."""
        code = """
from docpipe.core.operators.abstract_operator import AbstractOperator

class MissingShortName(AbstractOperator):
    category = "Extract"
    owner = "custom"
    def transform(self, table): pass
    @staticmethod
    def get_metadata(): pass
"""
        op_file = tmp_path / "missing_short_name.py"
        op_file.write_text(code, encoding="utf-8")

        with pytest.raises(CustomOperatorInvalidDataException, match="must define 'short_name'"):
            validate_operator_file(operator_file_path=op_file)

    def test_validate_non_literal_short_name_raises_exception(self, *, tmp_path: Path) -> None:
        """Test rejection when short_name is not a string literal."""
        code = """
from docpipe.core.operators.abstract_operator import AbstractOperator
NAME = "dynamic_name"

class DynamicShortName(AbstractOperator):
    short_name = NAME
    category = "Extract"
    owner = "custom"
    def transform(self, table): pass
    @staticmethod
    def get_metadata(): pass
"""
        op_file = tmp_path / "dynamic_short_name.py"
        op_file.write_text(code, encoding="utf-8")

        with pytest.raises(CustomOperatorInvalidDataException, match="short_name must be a string literal"):
            validate_operator_file(operator_file_path=op_file)

    def test_validate_owner_docpipe_raises_exception(self, *, tmp_path: Path) -> None:
        """Test rejection when custom operator attempts owner='docpipe'."""
        code = """
from docpipe.core.operators.abstract_operator import AbstractOperator

class FakeDocpipeOp(AbstractOperator):
    short_name = "fake_op"
    category = "Extract"
    owner = "docpipe"
    def transform(self, table): pass
    @staticmethod
    def get_metadata(): pass
"""
        op_file = tmp_path / "fake_docpipe.py"
        op_file.write_text(code, encoding="utf-8")

        with pytest.raises(CustomOperatorInvalidDataException, match="must set owner='custom'"):
            validate_operator_file(operator_file_path=op_file)

    def test_validate_missing_transform_raises_exception(self, *, tmp_path: Path) -> None:
        """Test rejection when transform method is missing."""
        code = """
from docpipe.core.operators.abstract_operator import AbstractOperator

class MissingTransform(AbstractOperator):
    short_name = "missing_transform"
    category = "Extract"
    owner = "custom"
    @staticmethod
    def get_metadata(): pass
"""
        op_file = tmp_path / "missing_transform.py"
        op_file.write_text(code, encoding="utf-8")

        with pytest.raises(CustomOperatorInvalidDataException, match="must implement 'transform' method"):
            validate_operator_file(operator_file_path=op_file)

    def test_validate_missing_get_metadata_static_raises_exception(self, *, tmp_path: Path) -> None:
        """Test rejection when get_metadata is not static."""
        code = """
from docpipe.core.operators.abstract_operator import AbstractOperator

class InstanceMetadata(AbstractOperator):
    short_name = "instance_metadata"
    category = "Extract"
    owner = "custom"
    def transform(self, table): pass
    def get_metadata(self): pass
"""
        op_file = tmp_path / "instance_metadata.py"
        op_file.write_text(code, encoding="utf-8")

        with pytest.raises(
            CustomOperatorInvalidDataException, match="must implement 'get_metadata' as a @staticmethod"
        ):
            validate_operator_file(operator_file_path=op_file)
