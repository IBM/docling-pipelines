"""Unit tests for FilesystemAdapter."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.orchestration.operator_loader.adapters.filesystem_adapter import FilesystemAdapter
from docpipe.core.orchestration.operator_loader.ports.operator_source import OperatorInfo


class TestFilesystemAdapterInitialization:
    """Test FilesystemAdapter initialization."""

    def test_init_with_valid_directory(self, tmp_path):
        """Test initialization with valid directory."""
        adapter = FilesystemAdapter(str(tmp_path))
        assert adapter.path == tmp_path.resolve()
        assert adapter._is_single_file is False
        assert adapter._loaded_modules == {}

    def test_init_with_valid_file(self, tmp_path):
        """Test initialization with valid Python file."""
        py_file = tmp_path / "test_operator.py"
        py_file.write_text("# Test operator")

        adapter = FilesystemAdapter(str(py_file))
        assert adapter.path == py_file.resolve()
        assert adapter._is_single_file is True

    def test_init_with_nonexistent_path(self):
        """Test initialization with nonexistent path raises ValueError."""
        with pytest.raises(ValueError, match="Operator path does not exist"):
            FilesystemAdapter("/nonexistent/path")

    def test_init_with_non_python_file(self, tmp_path):
        """Test initialization with non-Python file raises ValueError."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Not a Python file")

        with pytest.raises(ValueError, match="File must be a Python file"):
            FilesystemAdapter(str(txt_file))


class TestClearCache:
    """Test cache clearing functionality."""

    def test_clear_cache_removes_modules(self, tmp_path):
        """Test that clear_cache removes cached modules."""
        py_file = tmp_path / "test_op.py"
        py_file.write_text("""
from docpipe.core.operators.abstract_operator import AbstractOperator

class TestOp(AbstractOperator):
    SHORT_NAME = "test_op"
    CATEGORY = "test"

    def transform(self, table):
        return table
""")

        adapter = FilesystemAdapter(str(py_file))

        # Load a module to populate cache
        module = adapter._load_module_from_file(file_path=py_file)
        cache_key = str(py_file)
        adapter._loaded_modules[cache_key] = module

        # Verify module is cached
        assert cache_key in adapter._loaded_modules
        assert module.__name__ in sys.modules

        # Clear cache
        adapter.clear_cache()

        # Verify cache is cleared
        assert len(adapter._loaded_modules) == 0
        assert module.__name__ not in sys.modules


class TestListOperators:
    """Test operator discovery."""

    def test_list_operators_single_file(self, tmp_path):
        """Test listing operators from a single file."""
        py_file = tmp_path / "custom_operator.py"
        py_file.write_text("""
import pyarrow as pa
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory

class CustomOp(AbstractOperator):
    short_name: str = "custom_op"
    category: OperatorCategory = OperatorCategory.Functional

    def transform(self, table: pa.Table, file_name: str | None = None):
        return [table], {}
""")

        adapter = FilesystemAdapter(str(py_file))
        operators = adapter.list_operators()

        assert len(operators) == 1
        assert operators[0].short_name == "custom_op"
        assert operators[0].name == "CustomOp"
        assert operators[0].category == "Functional"

    def test_list_operators_directory(self, tmp_path):
        """Test listing operators from a directory."""
        # Create multiple operator files
        op1_file = tmp_path / "operator1.py"
        op1_file.write_text("""
import pyarrow as pa
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory

class Operator1(AbstractOperator):
    short_name: str = "op1"
    category: OperatorCategory = OperatorCategory.Functional

    def transform(self, table: pa.Table, file_name: str | None = None):
        return [table], {}
""")

        op2_file = tmp_path / "operator2.py"
        op2_file.write_text("""
import pyarrow as pa
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory

class Operator2(AbstractOperator):
    short_name: str = "op2"
    category: OperatorCategory = OperatorCategory.Quality

    def transform(self, table: pa.Table, file_name: str | None = None):
        return [table], {}
""")

        adapter = FilesystemAdapter(str(tmp_path))
        operators = adapter.list_operators()

        assert len(operators) == 2
        short_names = {op.short_name for op in operators}
        assert short_names == {"op1", "op2"}

    def test_list_operators_skips_private_files(self, tmp_path):
        """Test that private files are skipped."""
        # Create __init__.py
        init_file = tmp_path / "__init__.py"
        init_file.write_text("")

        # Create _private.py
        private_file = tmp_path / "_private.py"
        private_file.write_text("""
import pyarrow as pa
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory

class PrivateOp(AbstractOperator):
    short_name: str = "private_op"
    category: OperatorCategory = OperatorCategory.Functional

    def transform(self, table: pa.Table, file_name: str | None = None):
        return [table], {}
""")

        # Create valid operator
        op_file = tmp_path / "operator.py"
        op_file.write_text("""
import pyarrow as pa
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory

class ValidOp(AbstractOperator):
    short_name: str = "valid_op"
    category: OperatorCategory = OperatorCategory.Functional

    def transform(self, table: pa.Table, file_name: str | None = None):
        return [table], {}
""")

        adapter = FilesystemAdapter(str(tmp_path))
        operators = adapter.list_operators()

        # Should only find valid_op, not private_op
        assert len(operators) == 1
        assert operators[0].short_name == "valid_op"

    def test_list_operators_handles_invalid_files(self, tmp_path):
        """Test that invalid files are handled gracefully."""
        # Create file with syntax error
        bad_file = tmp_path / "bad_operator.py"
        bad_file.write_text("this is not valid python syntax !!!")

        # Create valid operator
        good_file = tmp_path / "good_operator.py"
        good_file.write_text("""
import pyarrow as pa
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory

class GoodOp(AbstractOperator):
    short_name: str = "good_op"
    category: OperatorCategory = OperatorCategory.Functional

    def transform(self, table: pa.Table, file_name: str | None = None):
        return [table], {}
""")

        adapter = FilesystemAdapter(str(tmp_path))
        operators = adapter.list_operators()

        # Should only find good_op, bad file should be skipped with warning
        assert len(operators) == 1
        assert operators[0].short_name == "good_op"


class TestLoadOperator:
    """Test operator loading."""

    def test_load_operator_single_file(self, tmp_path):
        """Test loading operator from single file."""
        py_file = tmp_path / "operator.py"
        py_file.write_text("""
from docpipe.core.operators.abstract_operator import AbstractOperator

class TestOperator(AbstractOperator):
    SHORT_NAME = "test_op"
    CATEGORY = "functional"

    def transform(self, table):
        return table
""")

        adapter = FilesystemAdapter(str(py_file))
        op_info = OperatorInfo(
            name="TestOperator",
            short_name="test_op",
            module_path=py_file.name,
            category="functional",
            source_location=f"filesystem:{py_file}",
        )

        module = adapter.load_operator(operator_info=op_info)
        assert hasattr(module, "TestOperator")

    def test_load_operator_from_directory(self, tmp_path):
        """Test loading operator from directory."""
        op_file = tmp_path / "my_operator.py"
        op_file.write_text("""
from docpipe.core.operators.abstract_operator import AbstractOperator

class MyOperator(AbstractOperator):
    SHORT_NAME = "my_op"
    CATEGORY = "functional"

    def transform(self, table):
        return table
""")

        adapter = FilesystemAdapter(str(tmp_path))
        op_info = OperatorInfo(
            name="MyOperator",
            short_name="my_op",
            module_path="my_operator.py",
            category="functional",
            source_location=f"filesystem:{tmp_path}",
        )

        module = adapter.load_operator(operator_info=op_info)
        assert hasattr(module, "MyOperator")

    def test_load_operator_uses_cache(self, tmp_path):
        """Test that loading same operator uses cache."""
        py_file = tmp_path / "operator.py"
        py_file.write_text("""
from docpipe.core.operators.abstract_operator import AbstractOperator

class CachedOp(AbstractOperator):
    SHORT_NAME = "cached_op"
    CATEGORY = "functional"

    def transform(self, table):
        return table
""")

        adapter = FilesystemAdapter(str(py_file))
        op_info = OperatorInfo(
            name="CachedOp",
            short_name="cached_op",
            module_path=py_file.name,
            category="functional",
            source_location=f"filesystem:{py_file}",
        )

        # Load first time
        module1 = adapter.load_operator(operator_info=op_info)

        # Load second time - should use cache
        module2 = adapter.load_operator(operator_info=op_info)

        assert module1 is module2

    def test_load_operator_nonexistent_file(self, tmp_path):
        """Test loading nonexistent operator raises FileNotFoundError."""
        adapter = FilesystemAdapter(str(tmp_path))
        op_info = OperatorInfo(
            name="NonExistent",
            short_name="nonexistent",
            module_path="nonexistent.py",
            category="functional",
            source_location=f"filesystem:{tmp_path}",
        )

        with pytest.raises(FileNotFoundError, match="Operator file not found"):
            adapter.load_operator(operator_info=op_info)


class TestValidateOperator:
    """Test operator validation."""

    def test_validate_operator_calls_validator(self, tmp_path):
        """Test that validate_operator delegates to OperatorValidator."""
        py_file = tmp_path / "operator.py"
        py_file.write_text("""
from docpipe.core.operators.abstract_operator import AbstractOperator

class ValidOp(AbstractOperator):
    SHORT_NAME = "valid_op"
    CATEGORY = "functional"

    def transform(self, table):
        return table
""")

        adapter = FilesystemAdapter(str(py_file))
        module = adapter._load_module_from_file(file_path=py_file)
        op_info = OperatorInfo(
            name="ValidOp",
            short_name="valid_op",
            module_path=py_file.name,
            category="functional",
            source_location=f"filesystem:{py_file}",
        )

        with patch(
            "docpipe.core.orchestration.operator_loader.adapters.filesystem_adapter.OperatorValidator.validate_module"
        ) as mock_validate:
            mock_validate.return_value = MagicMock(is_valid=True, errors=[])

            _ = adapter.validate_operator(module=module, operator_info=op_info)

            mock_validate.assert_called_once_with(module=module, operator_info=op_info)


class TestLoadModuleFromFile:
    """Test module loading from file."""

    def test_load_module_from_file_success(self, tmp_path):
        """Test successful module loading."""
        py_file = tmp_path / "test_module.py"
        py_file.write_text("""
TEST_CONSTANT = "test_value"

def test_function():
    return "test"
""")

        adapter = FilesystemAdapter(str(tmp_path))
        module = adapter._load_module_from_file(file_path=py_file)

        assert hasattr(module, "TEST_CONSTANT")
        assert module.TEST_CONSTANT == "test_value"
        assert hasattr(module, "test_function")

    def test_load_module_from_file_with_syntax_error(self, tmp_path):
        """Test loading file with syntax error raises ImportError."""
        py_file = tmp_path / "bad_syntax.py"
        py_file.write_text("this is not valid python !!!")

        adapter = FilesystemAdapter(str(tmp_path))

        with pytest.raises(ImportError, match="Failed to execute module"):
            adapter._load_module_from_file(file_path=py_file)


class TestFindOperatorClasses:
    """Test finding operator classes in modules."""

    def test_find_operator_classes_finds_operators(self, tmp_path):
        """Test finding operator classes in a module."""
        py_file = tmp_path / "operators.py"
        py_file.write_text("""
from docpipe.core.operators.abstract_operator import AbstractOperator

class Operator1(AbstractOperator):
    SHORT_NAME = "op1"
    CATEGORY = "functional"

    def transform(self, table):
        return table

class Operator2(AbstractOperator):
    SHORT_NAME = "op2"
    CATEGORY = "quality"

    def transform(self, table):
        return table

class NotAnOperator:
    pass
""")

        adapter = FilesystemAdapter(str(py_file))
        module = adapter._load_module_from_file(file_path=py_file)
        operators = adapter._find_operator_classes(module=module)

        assert len(operators) == 2
        operator_names = {op.__name__ for op in operators}
        assert operator_names == {"Operator1", "Operator2"}

    def test_find_operator_classes_excludes_abstract_operator(self, tmp_path):
        """Test that AbstractOperator itself is not included."""
        py_file = tmp_path / "test.py"
        py_file.write_text("""
from docpipe.core.operators.abstract_operator import AbstractOperator

# Just importing AbstractOperator, no custom operators
""")

        adapter = FilesystemAdapter(str(py_file))
        module = adapter._load_module_from_file(file_path=py_file)
        operators = adapter._find_operator_classes(module=module)

        assert len(operators) == 0

    def test_find_operator_classes_excludes_imported_operators(self, tmp_path):
        """Test that imported operators from other modules are excluded."""
        # Create first module with operator
        op1_file = tmp_path / "operator1.py"
        op1_file.write_text("""
from docpipe.core.operators.abstract_operator import AbstractOperator

class ImportedOp(AbstractOperator):
    SHORT_NAME = "imported_op"
    CATEGORY = "functional"

    def transform(self, table):
        return table
""")

        # Create second module that imports from first
        op2_file = tmp_path / "operator2.py"
        op2_file.write_text(
            """
from docpipe.core.operators.abstract_operator import AbstractOperator
import sys
sys.path.insert(0, str(tmp_path))

class LocalOp(AbstractOperator):
    SHORT_NAME = "local_op"
    CATEGORY = "functional"

    def transform(self, table):
        return table
""".replace("tmp_path", f"'{tmp_path}'")
        )

        adapter = FilesystemAdapter(str(op2_file))
        module = adapter._load_module_from_file(file_path=op2_file)
        operators = adapter._find_operator_classes(module=module)

        # Should only find LocalOp, not ImportedOp
        assert len(operators) == 1
        assert operators[0].__name__ == "LocalOp"


class TestAdapterMetadata:
    """Test adapter metadata."""

    def test_adapter_name(self, tmp_path):
        """Test adapter name constant."""
        adapter = FilesystemAdapter(str(tmp_path))
        assert adapter.ADAPTER_NAME == "filesystem"

    def test_adapter_display_name(self, tmp_path):
        """Test adapter display name constant."""
        adapter = FilesystemAdapter(str(tmp_path))
        assert adapter.ADAPTER_DISPLAY_NAME == "Local Filesystem"
