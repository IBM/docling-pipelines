"""Unit tests for global_config display module."""

from docpipe.core.orchestration.global_config_metadata import (
    EXECUTION_CONTROL,
    INCREMENTAL_PROCESSING,
    ORCHESTRATION,
    GlobalConfigMetadata,
    GlobalConfigParam,
)
from docpipe.utils.global_config.display import (
    display_global_config_summary,
    format_global_config_details,
    list_global_config,
)


class TestFormatGlobalConfigDetails:
    """Test format_global_config_details function."""

    def test_format_details_basic(self):
        """Test basic formatting of global config details."""
        params = {
            "test_param": GlobalConfigParam(
                name="test_param",
                type="bool",
                default=False,
                required=True,
                description="Test parameter description",
                category=EXECUTION_CONTROL,
            )
        }

        result = format_global_config_details(params)

        assert "test_param" in result
        assert "bool" in result
        assert "Test parameter description" in result
        assert EXECUTION_CONTROL in result

    def test_format_details_with_category_filter(self):
        """Test formatting with category filter."""
        params = GlobalConfigMetadata.get_all_config_metadata()

        result = format_global_config_details(params, category_filter=ORCHESTRATION)

        assert ORCHESTRATION in result
        assert "micro_batch_size" in result
        # Should not contain parameters from other categories
        assert "force_ingest" not in result

    def test_format_details_empty_category(self):
        """Test formatting with non-existent category."""
        params = GlobalConfigMetadata.get_all_config_metadata()

        result = format_global_config_details(params, category_filter="NonExistent")

        assert "No parameters found" in result
        assert "NonExistent" in result

    def test_format_details_multiple_categories(self):
        """Test formatting displays all categories when no filter."""
        params = GlobalConfigMetadata.get_all_config_metadata()

        result = format_global_config_details(params)

        assert EXECUTION_CONTROL in result
        assert INCREMENTAL_PROCESSING in result
        assert ORCHESTRATION in result


class TestDisplayGlobalConfigSummary:
    """Test display_global_config_summary function."""

    def test_summary_basic(self):
        """Test basic summary display."""
        result = display_global_config_summary()

        assert "GLOBAL CONFIGURATION PARAMETERS SUMMARY" in result
        assert "Parameter" in result
        assert "Type" in result
        assert "Category" in result
        assert "Required" in result
        assert "Default" in result
        assert "Total parameters:" in result

    def test_summary_with_category_filter(self):
        """Test summary with category filter."""
        result = display_global_config_summary(category_filter=EXECUTION_CONTROL)

        assert f"CATEGORY: {EXECUTION_CONTROL}" in result
        assert "disable_validation" in result
        # Should not contain parameters from other categories
        assert "micro_batch_size" not in result

    def test_summary_invalid_category(self):
        """Test summary with invalid category."""
        result = display_global_config_summary(category_filter="InvalidCategory")

        assert "No parameters found" in result
        assert "Available categories:" in result

    def test_summary_contains_all_parameters(self):
        """Test that summary contains all expected parameters."""
        result = display_global_config_summary()

        # Check for key parameters from each category
        assert "force_ingest" in result
        assert "micro_batch_size" in result
        assert "disable_validation" in result


class TestListGlobalConfig:
    """Test list_global_config function."""

    def test_list_summary_mode(self):
        """Test list in summary mode (verbose=False)."""
        result = list_global_config(verbose=False)

        assert "GLOBAL CONFIGURATION PARAMETERS SUMMARY" in result
        assert "Total parameters:" in result
        assert "Use --list-global-config --verbose" in result

    def test_list_verbose_mode(self):
        """Test list in verbose mode (verbose=True)."""
        result = list_global_config(verbose=True)

        assert "CATEGORY:" in result
        assert "Description:" in result
        # Should contain detailed information
        assert "Parameter:" in result

    def test_list_with_category_filter(self):
        """Test list with category filter."""
        result = list_global_config(verbose=False, category=ORCHESTRATION)

        assert ORCHESTRATION in result
        assert "micro_batch_size" in result

    def test_list_verbose_with_category(self):
        """Test list in verbose mode with category filter."""
        result = list_global_config(verbose=True, category=INCREMENTAL_PROCESSING)

        assert INCREMENTAL_PROCESSING in result
        assert "force_ingest" in result
        assert "Description:" in result

    def test_list_returns_string(self):
        """Test that list_global_config returns a string."""
        result = list_global_config()

        assert isinstance(result, str)
        assert len(result) > 0

    def test_list_all_categories_present(self):
        """Test that all categories are represented."""
        result = list_global_config(verbose=False)

        assert "Available categories:" in result
        assert EXECUTION_CONTROL in result
        assert INCREMENTAL_PROCESSING in result
        assert ORCHESTRATION in result
