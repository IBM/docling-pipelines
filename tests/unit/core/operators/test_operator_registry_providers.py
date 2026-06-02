"""
Unit tests for operator registry provider functionality and priority resolution.

Tests cover:
- External operator provider registration
- Priority-based operator resolution
- Operator deduplication by short_name
- Integration between registry and factory
"""

from unittest.mock import patch

import pytest

from datasift.core.constants.constants import DatasiftConstants
from datasift.core.operators.abstract_operator import AbstractOperator
from datasift.core.operators.operator_registry import (
    clear_operator_providers,
    get_datasift_operators,
    get_registered_provider_count,
    register_operator_provider,
)
from datasift.core.orchestration.operator_factory import OperatorFactory


# Mock operator classes for testing
class MockOSSOperator(AbstractOperator):
    """Mock OSS operator (priority 2)"""
    short_name = "mock_op"
    owner = DatasiftConstants.OWNER_DATASIFT

    @staticmethod
    def is_available():
        return True

    def transform(self, table, *, file_name: str = ""):
        return table, {}


class MockCustomOperator(AbstractOperator):
    """Mock custom operator (priority 1)"""
    short_name = "mock_op"
    owner = DatasiftConstants.OWNER_CUSTOM

    @staticmethod
    def is_available():
        return True

    def transform(self, table, *, file_name: str = ""):
        return table, {}


class MockEnterpriseOperator(AbstractOperator):
    """Mock enterprise operator (priority 0)"""
    short_name = "mock_op"
    owner = DatasiftConstants.OWNER_ENTERPRISE

    @staticmethod
    def is_available():
        return True

    def transform(self, table, *, file_name: str = ""):
        return table, {}


class MockUnavailableOperator(AbstractOperator):
    """Mock operator that is not available"""
    short_name = "unavailable_op"
    owner = DatasiftConstants.OWNER_DATASIFT

    @staticmethod
    def is_available():
        return False

    def transform(self, table, *, file_name: str = ""):
        return table, {}


class TestOperatorProviderRegistration:
    """Test external operator provider registration."""

    def setup_method(self):
        """Clear providers before each test."""
        clear_operator_providers()

    def teardown_method(self):
        """Clear providers after each test."""
        clear_operator_providers()

    def test_register_single_provider(self):
        """Test registering a single provider."""
        def my_provider(orchestrator=None):
            return frozenset()

        register_operator_provider(my_provider)
        assert get_registered_provider_count() == 1

    def test_register_multiple_providers(self):
        """Test registering multiple providers."""
        def provider1(orchestrator=None):
            return frozenset()

        def provider2(orchestrator=None):
            return frozenset()

        register_operator_provider(provider1)
        register_operator_provider(provider2)
        assert get_registered_provider_count() == 2

    def test_register_non_callable_raises_error(self):
        """Test that registering non-callable raises TypeError."""
        with pytest.raises(TypeError, match="Provider must be callable"):
            register_operator_provider("not_callable")

    def test_clear_providers(self):
        """Test clearing all providers."""
        def my_provider(orchestrator=None):
            return frozenset()

        register_operator_provider(my_provider)
        assert get_registered_provider_count() == 1

        clear_operator_providers()
        assert get_registered_provider_count() == 0


class TestPriorityResolution:
    """Test priority-based operator resolution."""

    def test_resolve_no_conflict(self):
        """Test resolution when no existing operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockOSSOperator,
            existing_operator=None,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
        )

        assert should_override is True
        assert new_priority == 2  # OSS priority
        assert existing_priority == float("inf")

    def test_enterprise_overrides_custom(self):
        """Test that enterprise operator overrides custom operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockEnterpriseOperator,
            existing_operator=MockCustomOperator,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
        )

        assert should_override is True
        assert new_priority == 0  # Enterprise priority
        assert existing_priority == 1  # Custom priority

    def test_enterprise_overrides_oss(self):
        """Test that enterprise operator overrides OSS operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockEnterpriseOperator,
            existing_operator=MockOSSOperator,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
        )

        assert should_override is True
        assert new_priority == 0  # Enterprise priority
        assert existing_priority == 2  # OSS priority

    def test_custom_overrides_oss(self):
        """Test that custom operator overrides OSS operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockCustomOperator,
            existing_operator=MockOSSOperator,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
        )

        assert should_override is True
        assert new_priority == 1  # Custom priority
        assert existing_priority == 2  # OSS priority

    def test_custom_cannot_override_enterprise(self):
        """Test that custom operator cannot override enterprise operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockCustomOperator,
            existing_operator=MockEnterpriseOperator,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
        )

        assert should_override is False
        assert new_priority == 1  # Custom priority
        assert existing_priority == 0  # Enterprise priority

    def test_oss_cannot_override_custom(self):
        """Test that OSS operator cannot override custom operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockOSSOperator,
            existing_operator=MockCustomOperator,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
        )

        assert should_override is False
        assert new_priority == 2  # OSS priority
        assert existing_priority == 1  # Custom priority

    def test_oss_cannot_override_enterprise(self):
        """Test that OSS operator cannot override enterprise operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockOSSOperator,
            existing_operator=MockEnterpriseOperator,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
        )

        assert should_override is False
        assert new_priority == 2  # OSS priority
        assert existing_priority == 0  # Enterprise priority

    def test_same_priority_allows_override(self):
        """Test that operators with same priority can override (last wins)."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockOSSOperator,
            existing_operator=MockOSSOperator,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
        )

        assert should_override is True
        assert new_priority == 2
        assert existing_priority == 2


class TestApplyPriorityResolution:
    """Test the apply_priority_resolution static method."""

    def test_add_operator_no_conflict(self):
        """Test adding operator when no conflict exists."""
        operators_dict: dict[str, type[AbstractOperator]] = {}

        result = OperatorFactory.apply_priority_resolution(
            new_operator=MockOSSOperator,
            operators_dict=operators_dict,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
            log_prefix="Test operator",
        )

        assert result is True
        assert "mock_op" in operators_dict
        assert operators_dict["mock_op"] == MockOSSOperator

    def test_override_with_higher_priority(self):
        """Test overriding operator with higher priority."""
        operators_dict: dict[str, type[AbstractOperator]] = {"mock_op": MockOSSOperator}

        result = OperatorFactory.apply_priority_resolution(
            new_operator=MockEnterpriseOperator,
            operators_dict=operators_dict,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
            log_prefix="Test operator",
        )

        assert result is True
        assert operators_dict["mock_op"] == MockEnterpriseOperator

    def test_reject_with_lower_priority(self):
        """Test rejecting operator with lower priority."""
        operators_dict: dict[str, type[AbstractOperator]] = {"mock_op": MockEnterpriseOperator}

        result = OperatorFactory.apply_priority_resolution(
            new_operator=MockOSSOperator,
            operators_dict=operators_dict,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
            log_prefix="Test operator",
        )

        assert result is False
        assert operators_dict["mock_op"] == MockEnterpriseOperator

    def test_operator_without_short_name(self):
        """Test handling operator without short_name attribute."""
        class BadOperator(AbstractOperator):
            # Missing short_name attribute
            owner = DatasiftConstants.OWNER_DATASIFT

            @staticmethod
            def is_available():
                return True

            def transform(self, table, *, file_name: str = ""):
                return table, {}

        # Remove short_name if it exists from parent
        if hasattr(BadOperator, 'short_name'):
            delattr(BadOperator, 'short_name')

        operators_dict: dict[str, type[AbstractOperator]] = {}

        result = OperatorFactory.apply_priority_resolution(
            new_operator=BadOperator,
            operators_dict=operators_dict,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
            log_prefix="Test operator",
        )

        assert result is False
        assert len(operators_dict) == 0


class TestOperatorAvailability:
    """Test operator availability filtering."""

    def test_unavailable_operator_skipped_in_factory(self):
        """Test that unavailable operators are skipped during loading."""
        # Mock get_datasift_operators to return unavailable operator
        with patch('datasift.core.operators.operator_registry.get_datasift_operators') as mock_get_ops:
            mock_get_ops.return_value = frozenset([MockUnavailableOperator])

            factory = OperatorFactory(orchestrator="python", enable_custom_operators=False)

            # Unavailable operator should not be in the factory
            assert "unavailable_op" not in factory.operators


class TestExternalProviderIntegration:
    """Test integration of external providers with registry."""

    def setup_method(self):
        """Clear providers before each test."""
        clear_operator_providers()

    def teardown_method(self):
        """Clear providers after each test."""
        clear_operator_providers()

    def test_external_provider_operators_included(self):
        """Test that operators from external providers are included."""
        class ExternalOperator(AbstractOperator):
            short_name = "external_op"
            owner = DatasiftConstants.OWNER_CUSTOM

            @staticmethod
            def is_available():
                return True

            def transform(self, table, *, file_name: str = ""):
                return table, {}

        def external_provider(orchestrator=None):
            return frozenset([ExternalOperator])

        register_operator_provider(external_provider)

        operators = get_datasift_operators()

        # Check that external operator is in the returned set
        operator_classes = {op.__name__ for op in operators}
        assert "ExternalOperator" in operator_classes

    def test_external_provider_with_orchestrator_filter(self):
        """Test that providers receive orchestrator parameter."""
        received_orchestrator = None

        def external_provider(orchestrator=None):
            nonlocal received_orchestrator
            received_orchestrator = orchestrator
            return frozenset()

        register_operator_provider(external_provider)
        get_datasift_operators(orchestrator="python")

        assert received_orchestrator == "python"

    def test_invalid_provider_return_type_handled(self):
        """Test that invalid provider return types are handled gracefully."""
        def bad_provider(orchestrator=None):
            return []  # Should return frozenset

        register_operator_provider(bad_provider)

        # Should not raise, just log warning
        operators = get_datasift_operators()
        assert isinstance(operators, frozenset)

    def test_provider_exception_handled(self):
        """Test that provider exceptions are handled gracefully."""
        def failing_provider(orchestrator=None):
            raise RuntimeError("Provider failed")

        register_operator_provider(failing_provider)

        # Should not raise, just log error
        operators = get_datasift_operators()
        assert isinstance(operators, frozenset)


class TestPriorityMapConfiguration:
    """Test priority map configuration."""

    def test_priority_map_values(self):
        """Test that priority map has correct values."""
        priority_map = DatasiftConstants.OPERATOR_PRIORITY_MAP

        assert priority_map[DatasiftConstants.OWNER_ENTERPRISE] == 0
        assert priority_map[DatasiftConstants.OWNER_CUSTOM] == 1
        assert priority_map[DatasiftConstants.OWNER_DATASIFT] == 2

    def test_unknown_owner_gets_lowest_priority(self):
        """Test that unknown owner gets lowest priority (infinity)."""
        class UnknownOwnerOperator(AbstractOperator):
            short_name = "unknown_op"
            owner = "unknown_owner"

            @staticmethod
            def is_available():
                return True

            def transform(self, table, *, file_name: str = ""):
                return table, {}

        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=UnknownOwnerOperator,
            existing_operator=MockOSSOperator,
            default_owner=DatasiftConstants.OWNER_DATASIFT,
        )

        assert should_override is False
        assert new_priority == float("inf")
        assert existing_priority == 2
