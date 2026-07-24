"""Unit tests for global_config_metadata module."""

from docpipe.core.orchestration.global_config_metadata import (
    EXECUTION_CONTROL,
    INCREMENTAL_PROCESSING,
    ORCHESTRATION,
    GlobalConfigMetadata,
    GlobalConfigParam,
)


class TestGlobalConfigParam:
    """Test GlobalConfigParam dataclass."""

    def test_global_config_param_creation(self):
        """Test creating a GlobalConfigParam instance."""
        param = GlobalConfigParam(
            name="test_param",
            type="bool",
            default=False,
            required=True,
            description="Test parameter",
            category=EXECUTION_CONTROL,
        )

        assert param.name == "test_param"
        assert param.type == "bool"
        assert param.default is False
        assert param.required is True
        assert param.description == "Test parameter"
        assert param.category == EXECUTION_CONTROL


class TestGlobalConfigMetadata:
    """Test GlobalConfigMetadata class."""

    def test_get_all_config_metadata(self):
        """Test retrieving all configuration metadata."""
        metadata = GlobalConfigMetadata.get_all_config_metadata()

        assert isinstance(metadata, dict)
        assert len(metadata) > 0
        assert "force_ingest" in metadata
        assert "micro_batch_size" in metadata
        assert isinstance(metadata["force_ingest"], GlobalConfigParam)

    def test_get_config_by_category(self):
        """Test retrieving configuration grouped by category."""
        by_category = GlobalConfigMetadata.get_config_by_category()

        assert isinstance(by_category, dict)
        assert EXECUTION_CONTROL in by_category
        assert INCREMENTAL_PROCESSING in by_category
        assert ORCHESTRATION in by_category

        # Verify each category contains GlobalConfigParam instances
        for category, params in by_category.items():
            assert isinstance(params, list)
            assert len(params) > 0
            for param in params:
                assert isinstance(param, GlobalConfigParam)
                assert param.category == category

    def test_get_categories(self):
        """Test retrieving list of categories."""
        categories = GlobalConfigMetadata.get_categories()

        assert isinstance(categories, list)
        assert len(categories) == 3
        assert EXECUTION_CONTROL in categories
        assert INCREMENTAL_PROCESSING in categories
        assert ORCHESTRATION in categories
        # Verify sorted order
        assert categories == sorted(categories)

    def test_parameter_attributes(self):
        """Test that all parameters have required attributes."""
        metadata = GlobalConfigMetadata.get_all_config_metadata()

        for _key, param in metadata.items():
            assert isinstance(param.name, str)
            assert len(param.name) > 0
            assert isinstance(param.type, str)
            assert isinstance(param.required, bool)
            assert isinstance(param.description, str)
            assert len(param.description) > 0
            assert param.category in [EXECUTION_CONTROL, INCREMENTAL_PROCESSING, ORCHESTRATION]

    def test_specific_parameters_exist(self):
        """Test that key parameters exist with correct properties."""
        metadata = GlobalConfigMetadata.get_all_config_metadata()

        # Test force_ingest
        assert "force_ingest" in metadata
        force_ingest = metadata["force_ingest"]
        assert force_ingest.type == "bool"
        assert force_ingest.default is False
        assert force_ingest.category == INCREMENTAL_PROCESSING

        # Test micro_batch_size
        assert "micro_batch_size" in metadata
        micro_batch = metadata["micro_batch_size"]
        assert micro_batch.type == "int"
        assert micro_batch.default == 100
        assert micro_batch.category == ORCHESTRATION

        # Test disable_validation
        assert "disable_validation" in metadata
        disable_val = metadata["disable_validation"]
        assert disable_val.type == "bool"
        assert disable_val.category == EXECUTION_CONTROL
