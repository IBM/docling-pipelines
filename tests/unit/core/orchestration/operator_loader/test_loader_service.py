"""
Unit tests for CustomOperatorLoader service.

Tests cover:
- Operator discovery from multiple sources
- Operator loading and validation
- Conflict detection and resolution
- Source configuration and initialization
- Error handling and edge cases
"""

from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from docpipe.core.operators.abstract_operator import AbstractOperator
from docpipe.core.orchestration.operator_loader.loader_service import CustomOperatorLoader
from docpipe.core.orchestration.operator_loader.ports.operator_source import (
    OperatorInfo,
    OperatorSourcePort,
    ValidationResult,
)


class MockOperator(AbstractOperator):
    """Mock operator for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def execute(self, **kwargs):
        pass


@pytest.fixture
def mock_operator_source():
    """Create mock operator source."""
    source = Mock(spec=OperatorSourcePort)
    source.ADAPTER_DISPLAY_NAME = "MockSource"
    source.list_operators.return_value = []
    source.clear_cache.return_value = None
    return source


@pytest.fixture
def sample_operator_info():
    """Create sample operator info."""
    return OperatorInfo(
        name="TestOperator",
        short_name="test_op",
        module_path="test.operators.test_operator",
        category="Functional",
        source_location="/path/to/operator.py",
    )


@pytest.fixture
def valid_validation_result():
    """Create valid validation result."""
    return ValidationResult(valid=True, errors=[], warnings=[])


@pytest.fixture
def invalid_validation_result():
    """Create invalid validation result."""
    return ValidationResult(valid=False, errors=["Validation error"], warnings=[])


class TestCustomOperatorLoaderInitialization:
    """Test CustomOperatorLoader initialization."""

    def test_init_with_sources(self, mock_operator_source):
        """Test initialization with sources."""
        loader = CustomOperatorLoader(sources=[mock_operator_source])
        assert len(loader.sources) == 1
        assert loader.loaded_operators == {}

    def test_init_with_multiple_sources(self):
        """Test initialization with multiple sources."""
        source1 = Mock(spec=OperatorSourcePort)
        source2 = Mock(spec=OperatorSourcePort)
        loader = CustomOperatorLoader(sources=[source1, source2])
        assert len(loader.sources) == 2

    def test_init_with_empty_sources(self):
        """Test initialization with empty sources list."""
        loader = CustomOperatorLoader(sources=[])
        assert loader.sources == []
        assert loader.loaded_operators == {}


class TestFromSourceConfigs:
    """Test loader creation from source configurations."""

    @patch("docpipe.core.orchestration.operator_loader.loader_service.OperatorSourceFactory.create")
    def test_from_source_configs_single(self, mock_factory, mock_operator_source):
        """Test creation from single source config."""
        mock_factory.return_value = mock_operator_source
        configs = [{"adapter_name": "filesystem", "path": "/test/path"}]

        loader = CustomOperatorLoader.from_source_configs(configs)

        assert len(loader.sources) == 1
        mock_factory.assert_called_once_with("filesystem", path="/test/path")

    @patch("docpipe.core.orchestration.operator_loader.loader_service.OperatorSourceFactory.create")
    def test_from_source_configs_multiple(self, mock_factory, mock_operator_source):
        """Test creation from multiple source configs."""
        mock_factory.return_value = mock_operator_source
        configs = [
            {"adapter_name": "filesystem", "path": "/test/path1"},
            {"adapter_name": "s3", "bucket": "test-bucket"},
        ]

        loader = CustomOperatorLoader.from_source_configs(configs)

        assert len(loader.sources) == 2
        assert mock_factory.call_count == 2

    @patch("docpipe.core.orchestration.operator_loader.loader_service.OperatorSourceFactory.create")
    def test_from_source_configs_empty(self, mock_factory):
        """Test creation from empty configs."""
        loader = CustomOperatorLoader.from_source_configs([])
        assert loader.sources == []
        mock_factory.assert_not_called()


class TestFromPaths:
    """Test loader creation from paths."""

    @patch("docpipe.core.orchestration.operator_loader.loader_service.OperatorSourceFactory.create")
    def test_from_paths_filesystem(self, mock_factory, mock_operator_source):
        """Test creation from filesystem path."""
        mock_factory.return_value = mock_operator_source
        paths = ["/absolute/path"]

        loader = CustomOperatorLoader.from_paths(paths)

        assert len(loader.sources) == 1
        mock_factory.assert_called_once_with("filesystem", path="/absolute/path")

    @patch("docpipe.core.orchestration.operator_loader.loader_service.OperatorSourceFactory.create")
    def test_from_paths_s3(self, mock_factory, mock_operator_source):
        """Test creation from S3 URI."""
        mock_factory.return_value = mock_operator_source
        paths = ["s3://bucket/path"]

        loader = CustomOperatorLoader.from_paths(paths)

        assert len(loader.sources) == 1
        mock_factory.assert_called_once_with("s3", uri="s3://bucket/path")

    @patch("docpipe.core.orchestration.operator_loader.loader_service.OperatorSourceFactory.create")
    def test_from_paths_package(self, mock_factory, mock_operator_source):
        """Test creation from package name."""
        mock_factory.return_value = mock_operator_source
        paths = ["my_package"]

        loader = CustomOperatorLoader.from_paths(paths)

        assert len(loader.sources) == 1
        mock_factory.assert_called_once_with("package", package_name="my_package")

    @patch("docpipe.core.orchestration.operator_loader.loader_service.OperatorSourceFactory.create")
    def test_from_paths_mixed(self, mock_factory, mock_operator_source):
        """Test creation from mixed path types."""
        mock_factory.return_value = mock_operator_source
        paths = ["/local/path", "s3://bucket/path", "package_name"]

        loader = CustomOperatorLoader.from_paths(paths)

        assert len(loader.sources) == 3

    @patch("docpipe.core.orchestration.operator_loader.loader_service.OperatorSourceFactory.create")
    def test_from_paths_package_import_error(self, mock_factory):
        """Test handling of package import errors."""
        mock_factory.side_effect = ImportError("Package not found")
        paths = ["nonexistent_package"]

        loader = CustomOperatorLoader.from_paths(paths)

        # Should skip invalid package
        assert len(loader.sources) == 0


class TestDiscoverOperators:
    """Test operator discovery."""

    def test_discover_operators_single_source(self, mock_operator_source, sample_operator_info):
        """Test discovering operators from single source."""
        mock_operator_source.list_operators.return_value = [sample_operator_info]
        loader = CustomOperatorLoader(sources=[mock_operator_source])

        discovered, source_map = loader.discover_operators()

        assert len(discovered) == 1
        assert "test_op" in discovered
        assert discovered["test_op"] == sample_operator_info
        assert sample_operator_info.source_location in source_map

    def test_discover_operators_multiple_sources(self, sample_operator_info):
        """Test discovering operators from multiple sources."""
        source1 = Mock(spec=OperatorSourcePort)
        source1.ADAPTER_DISPLAY_NAME = "Source1"
        source1.list_operators.return_value = [sample_operator_info]

        op_info2 = OperatorInfo(
            name="TestOperator2",
            short_name="test_op2",
            module_path="test.operators.test_operator2",
            category="Functional",
            source_location="/path/to/operator2.py",
        )
        source2 = Mock(spec=OperatorSourcePort)
        source2.ADAPTER_DISPLAY_NAME = "Source2"
        source2.list_operators.return_value = [op_info2]

        loader = CustomOperatorLoader(sources=[source1, source2])
        discovered, _ = loader.discover_operators()

        assert len(discovered) == 2
        assert "test_op" in discovered
        assert "test_op2" in discovered

    def test_discover_operators_duplicate_names(self, sample_operator_info):
        """Test handling of duplicate operator names."""
        source1 = Mock(spec=OperatorSourcePort)
        source1.ADAPTER_DISPLAY_NAME = "Source1"
        source1.list_operators.return_value = [sample_operator_info]

        # Same short_name, different source
        duplicate_info = OperatorInfo(
            name="DuplicateOperator",
            short_name="test_op",  # Same as sample_operator_info
            module_path="test.operators.duplicate",
            category="Functional",
            source_location="/different/path.py",
        )
        source2 = Mock(spec=OperatorSourcePort)
        source2.ADAPTER_DISPLAY_NAME = "Source2"
        source2.list_operators.return_value = [duplicate_info]

        loader = CustomOperatorLoader(sources=[source1, source2])
        discovered, _ = loader.discover_operators()

        # Should only have one operator (first discovered)
        assert len(discovered) == 1
        assert discovered["test_op"].source_location == sample_operator_info.source_location

    def test_discover_operators_with_clear_cache(self, mock_operator_source):
        """Test discovery with cache clearing."""
        loader = CustomOperatorLoader(sources=[mock_operator_source])
        loader.discover_operators(clear_cache=True)

        mock_operator_source.clear_cache.assert_called_once()

    def test_discover_operators_without_clear_cache(self, mock_operator_source):
        """Test discovery without cache clearing."""
        loader = CustomOperatorLoader(sources=[mock_operator_source])
        loader.discover_operators(clear_cache=False)

        mock_operator_source.clear_cache.assert_not_called()

    def test_discover_operators_source_error(self, sample_operator_info):
        """Test handling of source errors during discovery."""
        source1 = Mock(spec=OperatorSourcePort)
        source1.ADAPTER_DISPLAY_NAME = "Source1"
        source1.list_operators.side_effect = Exception("Discovery error")

        source2 = Mock(spec=OperatorSourcePort)
        source2.ADAPTER_DISPLAY_NAME = "Source2"
        source2.list_operators.return_value = [sample_operator_info]

        loader = CustomOperatorLoader(sources=[source1, source2])
        discovered, _ = loader.discover_operators()

        # Should continue with other sources despite error
        assert len(discovered) == 1
        assert "test_op" in discovered

    def test_discover_operators_empty_sources(self):
        """Test discovery with no sources."""
        loader = CustomOperatorLoader(sources=[])
        discovered, source_map = loader.discover_operators()

        assert discovered == {}
        assert source_map == {}


class TestLoadAndValidateOperator:
    """Test operator loading and validation."""

    def test_load_and_validate_success(self, mock_operator_source, sample_operator_info, valid_validation_result):
        """Test successful operator loading and validation."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"

        # Create a proper operator class with correct __module__
        class TestOperator(MockOperator):
            __module__ = "test_module"

        mock_module.TestOperator = TestOperator

        mock_operator_source.load_operator.return_value = mock_module
        mock_operator_source.validate_operator.return_value = valid_validation_result

        loader = CustomOperatorLoader(sources=[mock_operator_source])
        result = loader.load_and_validate_operator(sample_operator_info, mock_operator_source)

        assert result == TestOperator
        mock_operator_source.load_operator.assert_called_once_with(operator_info=sample_operator_info)
        mock_operator_source.validate_operator.assert_called_once()

    def test_load_and_validate_validation_failure(
        self, mock_operator_source, sample_operator_info, invalid_validation_result
    ):
        """Test operator loading with validation failure."""
        mock_module = ModuleType("test_module")
        mock_operator_source.load_operator.return_value = mock_module
        mock_operator_source.validate_operator.return_value = invalid_validation_result

        loader = CustomOperatorLoader(sources=[mock_operator_source])
        result = loader.load_and_validate_operator(sample_operator_info, mock_operator_source)

        assert result is None

    def test_load_and_validate_with_warnings(self, mock_operator_source, sample_operator_info):
        """Test operator loading with validation warnings."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"

        # Create a proper operator class with correct __module__
        class TestOperator(MockOperator):
            __module__ = "test_module"

        mock_module.TestOperator = TestOperator

        validation_result = ValidationResult(
            valid=True,
            errors=[],
            warnings=["Warning: Missing docstring"],
        )

        mock_operator_source.load_operator.return_value = mock_module
        mock_operator_source.validate_operator.return_value = validation_result

        loader = CustomOperatorLoader(sources=[mock_operator_source])
        result = loader.load_and_validate_operator(sample_operator_info, mock_operator_source)

        assert result == TestOperator

    def test_load_and_validate_load_error(self, mock_operator_source, sample_operator_info):
        """Test handling of load errors."""
        mock_operator_source.load_operator.side_effect = Exception("Load error")

        loader = CustomOperatorLoader(sources=[mock_operator_source])
        result = loader.load_and_validate_operator(sample_operator_info, mock_operator_source)

        assert result is None

    def test_load_and_validate_no_operator_class(
        self, mock_operator_source, sample_operator_info, valid_validation_result
    ):
        """Test handling when no operator class found in module."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"
        # Module has no operator class

        mock_operator_source.load_operator.return_value = mock_module
        mock_operator_source.validate_operator.return_value = valid_validation_result

        loader = CustomOperatorLoader(sources=[mock_operator_source])
        result = loader.load_and_validate_operator(sample_operator_info, mock_operator_source)

        assert result is None


class TestExtractOperatorClass:
    """Test operator class extraction from modules."""

    def test_extract_operator_class_success(self, sample_operator_info):
        """Test successful operator class extraction."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"

        # Create a proper operator class with correct __module__
        class TestOperator(MockOperator):
            __module__ = "test_module"

        mock_module.TestOperator = TestOperator

        loader = CustomOperatorLoader(sources=[])
        result = loader._extract_operator_class(mock_module, sample_operator_info)

        assert result == TestOperator

    def test_extract_operator_class_no_operator(self, sample_operator_info):
        """Test extraction when no operator in module."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"

        loader = CustomOperatorLoader(sources=[])
        result = loader._extract_operator_class(mock_module, sample_operator_info)

        assert result is None

    def test_extract_operator_class_abstract_operator(self, sample_operator_info):
        """Test extraction excludes AbstractOperator itself."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"
        mock_module.AbstractOperator = AbstractOperator

        loader = CustomOperatorLoader(sources=[])
        result = loader._extract_operator_class(mock_module, sample_operator_info)

        assert result is None

    def test_extract_operator_class_wrong_module(self, sample_operator_info):
        """Test extraction excludes classes from different modules."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"

        # Create operator with different module
        class WrongModuleOperator(AbstractOperator):
            __module__ = "different_module"

            def execute(self, **kwargs):
                pass

        mock_module.WrongModuleOperator = WrongModuleOperator

        loader = CustomOperatorLoader(sources=[])
        result = loader._extract_operator_class(mock_module, sample_operator_info)

        assert result is None


class TestValidateAndLoad:
    """Test complete validation and loading workflow."""

    def test_validate_and_load_success(self, mock_operator_source, sample_operator_info, valid_validation_result):
        """Test successful validation and loading."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"

        # Create a proper operator class with correct __module__
        class TestOperator(MockOperator):
            __module__ = "test_module"

        mock_module.TestOperator = TestOperator

        mock_operator_source.list_operators.return_value = [sample_operator_info]
        mock_operator_source.load_operator.return_value = mock_module
        mock_operator_source.validate_operator.return_value = valid_validation_result

        loader = CustomOperatorLoader(sources=[mock_operator_source])
        builtin_operators = {}

        result = loader.validate_and_load(builtin_operators)

        assert len(result) == 1
        assert "test_op" in result
        assert result["test_op"] == TestOperator

    def test_validate_and_load_no_operators(self, mock_operator_source):
        """Test validation and loading with no operators."""
        mock_operator_source.list_operators.return_value = []

        loader = CustomOperatorLoader(sources=[mock_operator_source])
        result = loader.validate_and_load({})

        assert result == {}

    def test_validate_and_load_with_clear_cache(
        self, mock_operator_source, sample_operator_info, valid_validation_result
    ):
        """Test validation and loading with cache clearing."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"

        # Create a proper operator class with correct __module__
        class TestOperator(MockOperator):
            __module__ = "test_module"

        mock_module.TestOperator = TestOperator

        mock_operator_source.list_operators.return_value = [sample_operator_info]
        mock_operator_source.load_operator.return_value = mock_module
        mock_operator_source.validate_operator.return_value = valid_validation_result

        loader = CustomOperatorLoader(sources=[mock_operator_source])
        result = loader.validate_and_load({}, clear_cache=True)

        mock_operator_source.clear_cache.assert_called_once()
        assert len(result) == 1

    def test_validate_and_load_partial_success(self, sample_operator_info):
        """Test validation and loading with some failures."""
        # First operator succeeds
        mock_module1 = ModuleType("test_module1")
        mock_module1.__name__ = "test_module1"

        # Create a proper operator class with correct __module__
        class TestOperator(MockOperator):
            __module__ = "test_module1"

        mock_module1.TestOperator = TestOperator

        source1 = Mock(spec=OperatorSourcePort)
        source1.ADAPTER_DISPLAY_NAME = "Source1"
        source1.list_operators.return_value = [sample_operator_info]
        source1.load_operator.return_value = mock_module1
        source1.validate_operator.return_value = ValidationResult(valid=True, errors=[], warnings=[])

        # Second operator fails
        op_info2 = OperatorInfo(
            name="FailOperator",
            short_name="fail_op",
            module_path="test.operators.fail",
            category="Functional",
            source_location="/path/to/fail.py",
        )
        source2 = Mock(spec=OperatorSourcePort)
        source2.ADAPTER_DISPLAY_NAME = "Source2"
        source2.list_operators.return_value = [op_info2]
        source2.load_operator.side_effect = Exception("Load error")

        loader = CustomOperatorLoader(sources=[source1, source2])
        result = loader.validate_and_load({})

        # Should have one successful operator
        assert len(result) == 1
        assert "test_op" in result

    def test_validate_and_load_missing_source(self, sample_operator_info):
        """Test handling when source not found in map."""
        source = Mock(spec=OperatorSourcePort)
        source.ADAPTER_DISPLAY_NAME = "TestSource"
        source.list_operators.return_value = [sample_operator_info]

        loader = CustomOperatorLoader(sources=[source])

        # Manually break the source map
        with patch.object(loader, "discover_operators") as mock_discover:
            mock_discover.return_value = ({"test_op": sample_operator_info}, {})  # Empty source map

            result = loader.validate_and_load({})

            # Should handle missing source gracefully
            assert result == {}

    def test_validate_and_load_updates_loaded_operators(
        self, mock_operator_source, sample_operator_info, valid_validation_result
    ):
        """Test that loaded operators are stored in instance."""
        mock_module = ModuleType("test_module")
        mock_module.__name__ = "test_module"

        # Create a proper operator class with correct __module__
        class TestOperator(MockOperator):
            __module__ = "test_module"

        mock_module.TestOperator = TestOperator

        mock_operator_source.list_operators.return_value = [sample_operator_info]
        mock_operator_source.load_operator.return_value = mock_module
        mock_operator_source.validate_operator.return_value = valid_validation_result

        loader = CustomOperatorLoader(sources=[mock_operator_source])
        loader.validate_and_load({})

        assert len(loader.loaded_operators) == 1
        assert "test_op" in loader.loaded_operators
