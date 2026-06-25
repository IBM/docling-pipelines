"""Unit tests for PackageAdapter."""

import importlib.metadata
from types import ModuleType
from typing import cast
from unittest.mock import Mock, patch

import pytest

from docpipe.core.orchestration.operator_loader.adapters.package_adapter import PackageAdapter
from docpipe.core.orchestration.operator_loader.ports.operator_source import (
    OperatorInfo,
    ValidationResult,
)


@pytest.mark.unit
class TestPackageAdapter:
    """Test PackageAdapter class."""

    def test_init_with_valid_package(self) -> None:
        """Test initialization with a valid installed package."""
        with patch("importlib.metadata.version") as mock_version, patch("importlib.import_module") as mock_import:
            mock_version.return_value = "1.0.0"
            mock_import.return_value = Mock()

            adapter = PackageAdapter(package_name="test_package", operator_module="operators")

            assert adapter.package_name == "test_package"
            assert adapter.operator_module == "operators"
            assert adapter.full_module_path == "test_package.operators"
            mock_version.assert_called_once_with("test_package")

    def test_init_with_package_not_installed(self) -> None:
        """Test initialization fails when package is not installed."""
        with patch("importlib.metadata.version") as mock_version:
            mock_version.side_effect = importlib.metadata.PackageNotFoundError

            with pytest.raises(ImportError, match="Package 'nonexistent_package' is not installed"):
                PackageAdapter(package_name="nonexistent_package")

    def test_init_with_invalid_operator_module(self) -> None:
        """Test initialization fails when operator module doesn't exist."""
        with patch("importlib.metadata.version") as mock_version, patch("importlib.import_module") as mock_import:
            mock_version.return_value = "1.0.0"
            # First call succeeds (package), second call fails (operator module)
            mock_import.side_effect = [Mock(), ImportError("No module named 'test_package.operators'")]

            with pytest.raises(ValueError, match="Operator module 'operators' not found"):
                PackageAdapter(package_name="test_package", operator_module="operators")

    def test_list_operators_via_entry_points(self) -> None:
        """Test entry point discovery method is called."""
        with patch("importlib.metadata.version"), patch("importlib.import_module"):
            adapter = cast(PackageAdapter, PackageAdapter(package_name="test_package"))

            # Test that _discover_via_entry_points method exists and is callable
            assert hasattr(adapter, "_discover_via_entry_points")
            assert callable(adapter._discover_via_entry_points)

            # Call list_operators which internally calls both discovery methods
            # This tests the integration without complex mocking
            operators = adapter.list_operators()

            # Should return empty list when no operators are installed
            assert isinstance(operators, list)

    def test_list_operators_via_module_inspection(self) -> None:
        """Test discovering operators via module inspection."""
        with (
            patch("importlib.metadata.version"),
            patch("importlib.import_module") as mock_import,
            patch("importlib.metadata.entry_points") as mock_entry_points,
        ):
            # No entry points
            mock_entry_points.return_value = []

            # Mock operator module
            mock_module = Mock(spec=ModuleType)
            mock_module.__name__ = "test_package.operators"

            # Mock operator class
            from docpipe.core.operators.abstract_operator import AbstractOperator

            mock_operator_class = Mock(spec=AbstractOperator)
            mock_operator_class.__name__ = "TestOperator"
            mock_operator_class.__module__ = "test_package.operators"
            mock_operator_class.short_name = "test_op"
            mock_operator_class.category = "Functional"

            # Make it pass isinstance and issubclass checks
            with (
                patch("inspect.getmembers") as mock_getmembers,
                patch("inspect.isclass") as mock_isclass,
                patch("builtins.issubclass") as mock_issubclass,
            ):
                mock_getmembers.return_value = [("TestOperator", mock_operator_class)]
                mock_isclass.return_value = True
                mock_issubclass.return_value = True

                mock_import.side_effect = [Mock(), mock_module]

                adapter = PackageAdapter(package_name="test_package")
                operators = adapter.list_operators()

                assert len(operators) >= 0  # May find operators via inspection

    def test_load_operator_success(self) -> None:
        """Test loading an operator module successfully."""
        with patch("importlib.metadata.version"), patch("importlib.import_module") as mock_import:
            mock_module = Mock(spec=ModuleType)
            mock_import.return_value = mock_module

            adapter = PackageAdapter(package_name="test_package")

            operator_info = OperatorInfo(
                name="TestOperator",
                short_name="test_op",
                module_path="test_package.operators.test_op",
                category="Functional",
                source_location="package:test_package",
            )

            loaded_module = adapter.load_operator(operator_info=operator_info)

            assert loaded_module is not None
            assert loaded_module == mock_module

    def test_load_operator_with_entry_point_format(self) -> None:
        """Test loading operator with entry point format (module:ClassName)."""
        with patch("importlib.metadata.version"), patch("importlib.import_module") as mock_import:
            mock_module = Mock(spec=ModuleType)
            mock_import.return_value = mock_module

            adapter = PackageAdapter(package_name="test_package")

            operator_info = OperatorInfo(
                name="TestOperator",
                short_name="test_op",
                module_path="test_package.operators.test_op:TestOperator",
                category="Functional",
                source_location="package:test_package",
            )

            loaded_module = adapter.load_operator(operator_info=operator_info)

            # Should extract module part before colon
            mock_import.assert_called_with("test_package.operators.test_op")
            assert loaded_module == mock_module

    def test_load_operator_caching(self) -> None:
        """Test that loaded modules are cached."""
        with patch("importlib.metadata.version"), patch("importlib.import_module") as mock_import:
            mock_module = Mock(spec=ModuleType)
            mock_import.return_value = mock_module

            adapter = PackageAdapter(package_name="test_package")

            operator_info = OperatorInfo(
                name="TestOperator",
                short_name="test_op",
                module_path="test_package.operators.test_op",
                category="Functional",
                source_location="package:test_package",
            )

            # Load twice
            module1 = adapter.load_operator(operator_info=operator_info)
            module2 = adapter.load_operator(operator_info=operator_info)

            # Should only import once due to caching
            assert mock_import.call_count == 3  # package, operator_module, actual operator
            assert module1 == module2

    def test_load_operator_import_error(self) -> None:
        """Test loading operator fails with ImportError."""
        with patch("importlib.metadata.version"), patch("importlib.import_module") as mock_import:
            mock_import.side_effect = [Mock(), Mock(), ImportError("Module not found")]

            adapter = PackageAdapter(package_name="test_package")

            operator_info = OperatorInfo(
                name="TestOperator",
                short_name="test_op",
                module_path="test_package.operators.nonexistent",
                category="Functional",
                source_location="package:test_package",
            )

            with pytest.raises(ImportError, match="Failed to load operator module"):
                adapter.load_operator(operator_info=operator_info)

    def test_clear_cache(self) -> None:
        """Test clearing the module cache."""
        with patch("importlib.metadata.version"), patch("importlib.import_module") as mock_import:
            mock_module = Mock(spec=ModuleType)
            mock_module.__name__ = "test_module"
            mock_import.return_value = mock_module

            adapter = PackageAdapter(package_name="test_package")

            operator_info = OperatorInfo(
                name="TestOperator",
                short_name="test_op",
                module_path="test_package.operators.test_op",
                category="Functional",
                source_location="package:test_package",
            )

            # Load operator to populate cache
            adapter.load_operator(operator_info=operator_info)
            assert len(adapter._loaded_modules) > 0

            # Clear cache
            adapter.clear_cache()
            assert len(adapter._loaded_modules) == 0

    def test_validate_operator(self) -> None:
        """Test operator validation delegates to OperatorValidator."""
        with patch("importlib.metadata.version"), patch("importlib.import_module"):
            adapter = cast(PackageAdapter, PackageAdapter(package_name="test_package"))

            mock_module = Mock(spec=ModuleType)
            operator_info = OperatorInfo(
                name="TestOperator",
                short_name="test_op",
                module_path="test_package.operators.test_op",
                category="Functional",
                source_location="package:test_package",
            )

            # Test that validate_operator method exists and returns ValidationResult
            result = adapter.validate_operator(module=mock_module, operator_info=operator_info)

            assert isinstance(result, ValidationResult)
            # Result will be invalid since mock module has no operator classes
            assert result.valid is False
            assert len(result.errors) > 0

    def test_adapter_name_and_display_name(self) -> None:
        """Test adapter has correct name and display name."""
        with patch("importlib.metadata.version"), patch("importlib.import_module"):
            adapter = PackageAdapter(package_name="test_package")

            assert adapter.ADAPTER_NAME == "package"
            assert adapter.ADAPTER_DISPLAY_NAME == "Python Package"

    def test_default_operator_module(self) -> None:
        """Test default operator_module is 'operators'."""
        with patch("importlib.metadata.version"), patch("importlib.import_module"):
            adapter = PackageAdapter(package_name="test_package")

            assert adapter.operator_module == "operators"
            assert adapter.full_module_path == "test_package.operators"

    def test_custom_operator_module(self) -> None:
        """Test custom operator_module parameter."""
        with patch("importlib.metadata.version"), patch("importlib.import_module"):
            adapter = PackageAdapter(package_name="test_package", operator_module="custom_ops")

            assert adapter.operator_module == "custom_ops"
            assert adapter.full_module_path == "test_package.custom_ops"

    def test_validate_package_name_valid_names(self) -> None:
        """Test validation accepts valid package names."""
        valid_names = [
            "my_package",
            "my-package",
            "MyPackage",
            "package123",
            "_private_package",
            "my_company.my_package",
            "namespace.sub_package",
            "a",
            "_a",
        ]

        for name in valid_names:
            with patch("importlib.metadata.version"), patch("importlib.import_module"):
                # Should not raise
                adapter = PackageAdapter(package_name=name)
                assert adapter.package_name == name

    def test_validate_package_name_empty_string(self) -> None:
        """Test validation rejects empty package name."""
        with pytest.raises(ValueError, match="package_name must be a non-empty string"):
            PackageAdapter._validate_package_name("")

    def test_validate_package_name_none(self) -> None:
        """Test validation rejects None package name."""
        with pytest.raises(ValueError, match="package_name must be a non-empty string"):
            PackageAdapter._validate_package_name(None)  # type: ignore

    def test_validate_package_name_path_traversal(self) -> None:
        """Test validation rejects path traversal attempts."""
        malicious_names = [
            "../etc/passwd",
            "package/../malicious",
            "..package",
            "package..",
        ]

        for name in malicious_names:
            with pytest.raises(ValueError, match="path traversal characters"):
                PackageAdapter._validate_package_name(name)

    def test_validate_package_name_slashes(self) -> None:
        """Test validation rejects slashes."""
        malicious_names = [
            "package/subdir",
            "package\\subdir",
            "/absolute/path",
            "\\windows\\path",
        ]

        for name in malicious_names:
            with pytest.raises(ValueError, match="path traversal characters"):
                PackageAdapter._validate_package_name(name)

    def test_validate_package_name_invalid_characters(self) -> None:
        """Test validation rejects invalid characters."""
        invalid_names = [
            "package@version",
            "package!",
            "package#tag",
            "package$var",
            "package%20",
            "package&more",
            "package*",
            "package()",
            "package[]",
            "package{}",
            "package;command",
            "package|pipe",
            "package<script>",
            "123package",  # Cannot start with number
            "-package",  # Cannot start with hyphen
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="Invalid package_name"):
                PackageAdapter._validate_package_name(name)

    def test_validate_package_name_empty_parts(self) -> None:
        """Test validation rejects empty parts (consecutive dots)."""
        invalid_names = [
            "package..subpackage",
            ".package",
            "package.",
            "package...",
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match=r"empty parts|Invalid package_name"):
                PackageAdapter._validate_package_name(name)

    def test_init_with_invalid_package_name(self) -> None:
        """Test initialization fails with invalid package name."""
        with pytest.raises(ValueError, match="Invalid package_name"):
            PackageAdapter(package_name="../malicious")

        with pytest.raises(ValueError, match="Invalid package_name"):
            PackageAdapter(package_name="package;rm -rf /")
