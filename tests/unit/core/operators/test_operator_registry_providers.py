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

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.operators.abstract_operator import AbstractOperator
from docpipe.core.operators.operator_registry import (
    clear_operator_providers,
    get_docpipe_operators,
    get_registered_provider_count,
    register_operator_provider,
)
from docpipe.core.orchestration.operator_factory import OperatorFactory


# Mock operator classes for testing
class MockOSSOperator(AbstractOperator):
    """Mock OSS operator (priority 2)"""

    short_name = "mock_op"
    owner = DocpipeConstants.OWNER_DOCPIPE

    @staticmethod
    def is_available():
        return True

    def transform(self, table, *, file_name: str = ""):
        return table, {}


class MockCustomOperator(AbstractOperator):
    """Mock custom operator (priority 1)"""

    short_name = "mock_op"
    owner = DocpipeConstants.OWNER_CUSTOM

    @staticmethod
    def is_available():
        return True

    def transform(self, table, *, file_name: str = ""):
        return table, {}


MOCK_HIGH_PRIORITY_OWNER = "mock_high_priority"
MOCK_HIGH_PRIORITY = 10  # below 100 (OWNER_CUSTOM), so outranks all built-in tiers


class MockHighPriorityOperator(AbstractOperator):
    """Mock operator registered with a consumer-defined high-priority tier (priority 10)."""

    short_name = "mock_op"
    owner = MOCK_HIGH_PRIORITY_OWNER

    @staticmethod
    def is_available():
        return True

    def transform(self, table, *, file_name: str = ""):
        return table, {}


class MockUnavailableOperator(AbstractOperator):
    """Mock operator that is not available"""

    short_name = "unavailable_op"
    owner = DocpipeConstants.OWNER_DOCPIPE

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

    def setup_method(self):
        """Register the mock high-priority tier before each test."""
        OperatorFactory.register_owner_priority(owner=MOCK_HIGH_PRIORITY_OWNER, priority=MOCK_HIGH_PRIORITY)

    def teardown_method(self):
        """Remove the mock tier after each test to avoid polluting global state."""
        DocpipeConstants.OPERATOR_PRIORITY_MAP.pop(MOCK_HIGH_PRIORITY_OWNER, None)

    def test_resolve_no_conflict(self):
        """Test resolution when no existing operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockOSSOperator,
            existing_operator=None,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
        )

        assert should_override is True
        assert new_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]
        assert existing_priority == float("inf")

    def test_high_priority_overrides_custom(self):
        """Test that a registered high-priority operator overrides a custom operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockHighPriorityOperator,
            existing_operator=MockCustomOperator,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
        )

        assert should_override is True
        assert new_priority == MOCK_HIGH_PRIORITY
        assert existing_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_CUSTOM]

    def test_high_priority_overrides_oss(self):
        """Test that a registered high-priority operator overrides an OSS operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockHighPriorityOperator,
            existing_operator=MockOSSOperator,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
        )

        assert should_override is True
        assert new_priority == MOCK_HIGH_PRIORITY
        assert existing_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]

    def test_custom_overrides_oss(self):
        """Test that custom operator overrides OSS operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockCustomOperator,
            existing_operator=MockOSSOperator,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
        )

        assert should_override is True
        assert new_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_CUSTOM]
        assert existing_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]

    def test_custom_cannot_override_high_priority(self):
        """Test that custom operator cannot override a higher-priority registered operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockCustomOperator,
            existing_operator=MockHighPriorityOperator,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
        )

        assert should_override is False
        assert new_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_CUSTOM]
        assert existing_priority == MOCK_HIGH_PRIORITY

    def test_oss_cannot_override_custom(self):
        """Test that OSS operator cannot override custom operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockOSSOperator,
            existing_operator=MockCustomOperator,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
        )

        assert should_override is False
        assert new_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]
        assert existing_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_CUSTOM]

    def test_oss_cannot_override_high_priority(self):
        """Test that OSS operator cannot override a higher-priority registered operator."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockOSSOperator,
            existing_operator=MockHighPriorityOperator,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
        )

        assert should_override is False
        assert new_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]
        assert existing_priority == MOCK_HIGH_PRIORITY

    def test_same_priority_allows_override(self):
        """Test that operators with same priority can override (last wins)."""
        should_override, new_priority, existing_priority = OperatorFactory.resolve_operator_by_priority(
            new_operator=MockOSSOperator,
            existing_operator=MockOSSOperator,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
        )

        assert should_override is True
        assert new_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]
        assert existing_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]


class TestApplyPriorityResolution:
    """Test the apply_priority_resolution static method."""

    def test_add_operator_no_conflict(self):
        """Test adding operator when no conflict exists."""
        operators_dict: dict[str, type[AbstractOperator]] = {}

        result = OperatorFactory.apply_priority_resolution(
            new_operator=MockOSSOperator,
            operators_dict=operators_dict,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
            log_prefix="Test operator",
        )

        assert result is True
        assert "mock_op" in operators_dict
        assert operators_dict["mock_op"] == MockOSSOperator

    def test_override_with_higher_priority(self):
        """Test overriding operator with higher priority."""
        OperatorFactory.register_owner_priority(owner=MOCK_HIGH_PRIORITY_OWNER, priority=MOCK_HIGH_PRIORITY)
        operators_dict: dict[str, type[AbstractOperator]] = {"mock_op": MockOSSOperator}

        try:
            result = OperatorFactory.apply_priority_resolution(
                new_operator=MockHighPriorityOperator,
                operators_dict=operators_dict,
                default_owner=DocpipeConstants.OWNER_DOCPIPE,
                log_prefix="Test operator",
            )

            assert result is True
            assert operators_dict["mock_op"] == MockHighPriorityOperator
        finally:
            DocpipeConstants.OPERATOR_PRIORITY_MAP.pop(MOCK_HIGH_PRIORITY_OWNER, None)

    def test_reject_with_lower_priority(self):
        """Test rejecting operator with lower priority."""
        OperatorFactory.register_owner_priority(owner=MOCK_HIGH_PRIORITY_OWNER, priority=MOCK_HIGH_PRIORITY)
        operators_dict: dict[str, type[AbstractOperator]] = {"mock_op": MockHighPriorityOperator}

        try:
            result = OperatorFactory.apply_priority_resolution(
                new_operator=MockOSSOperator,
                operators_dict=operators_dict,
                default_owner=DocpipeConstants.OWNER_DOCPIPE,
                log_prefix="Test operator",
            )

            assert result is False
            assert operators_dict["mock_op"] == MockHighPriorityOperator
        finally:
            DocpipeConstants.OPERATOR_PRIORITY_MAP.pop(MOCK_HIGH_PRIORITY_OWNER, None)

    def test_operator_without_short_name(self):
        """Test handling operator without short_name attribute."""

        class BadOperator(AbstractOperator):
            # Missing short_name attribute
            owner = DocpipeConstants.OWNER_DOCPIPE

            @staticmethod
            def is_available():
                return True

            def transform(self, table, *, file_name: str = ""):
                return table, {}

        # Remove short_name if it exists from parent
        if hasattr(BadOperator, "short_name"):
            delattr(BadOperator, "short_name")

        operators_dict: dict[str, type[AbstractOperator]] = {}

        result = OperatorFactory.apply_priority_resolution(
            new_operator=BadOperator,
            operators_dict=operators_dict,
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
            log_prefix="Test operator",
        )

        assert result is False
        assert len(operators_dict) == 0


class TestOperatorAvailability:
    """Test operator availability filtering."""

    def test_unavailable_operator_skipped_in_factory(self):
        """Test that unavailable operators are skipped during loading."""
        # Mock get_docpipe_operators to return unavailable operator
        with patch("docpipe.core.operators.operator_registry.get_docpipe_operators") as mock_get_ops:
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
            owner = DocpipeConstants.OWNER_CUSTOM

            @staticmethod
            def is_available():
                return True

            def transform(self, table, *, file_name: str = ""):
                return table, {}

        def external_provider(orchestrator=None):
            return frozenset([ExternalOperator])

        register_operator_provider(external_provider)

        operators = get_docpipe_operators()

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
        get_docpipe_operators(orchestrator="python")

        assert received_orchestrator == "python"

    def test_invalid_provider_return_type_handled(self):
        """Test that invalid provider return types are handled gracefully."""

        def bad_provider(orchestrator=None):
            return []  # Should return frozenset

        register_operator_provider(bad_provider)

        # Should not raise, just log warning
        operators = get_docpipe_operators()
        assert isinstance(operators, frozenset)

    def test_provider_exception_handled(self):
        """Test that provider exceptions are handled gracefully."""

        def failing_provider(orchestrator=None):
            raise RuntimeError("Provider failed")

        register_operator_provider(failing_provider)

        # Should not raise, just log error
        operators = get_docpipe_operators()
        assert isinstance(operators, frozenset)


class TestPriorityMapConfiguration:
    """Test priority map configuration."""

    def test_priority_map_builtin_values(self):
        """Test that built-in priority map entries have the expected spaced values."""
        priority_map = DocpipeConstants.OPERATOR_PRIORITY_MAP

        assert priority_map[DocpipeConstants.OWNER_CUSTOM] == 100
        assert priority_map[DocpipeConstants.OWNER_DOCPIPE] == 200
        assert DocpipeConstants.OPERATOR_PRIORITY_MAP.get("docpipe_enterprise") is None

    def test_custom_has_higher_precedence_than_docpipe(self):
        """Test that custom priority value is lower (higher precedence) than docpipe."""
        assert (
            DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_CUSTOM]
            < DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]
        )

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
            default_owner=DocpipeConstants.OWNER_DOCPIPE,
        )

        assert should_override is False
        assert new_priority == float("inf")
        assert existing_priority == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]

    def test_register_owner_priority_adds_to_map(self):
        """Test that register_owner_priority correctly inserts the new tier."""
        owner = "test_registered_owner"
        priority = 50
        try:
            OperatorFactory.register_owner_priority(owner=owner, priority=priority)
            assert DocpipeConstants.OPERATOR_PRIORITY_MAP[owner] == priority
        finally:
            DocpipeConstants.OPERATOR_PRIORITY_MAP.pop(owner, None)

    def test_register_owner_priority_affects_resolution(self):
        """Test that registered tiers are respected during resolution, including ordering between two registered tiers."""
        app_owner = "test_app_tier"  # priority 10: above all built-ins
        plugin_owner = "test_plugin_tier"  # priority 50: above OWNER_CUSTOM (100), below app

        OperatorFactory.register_owner_priority(owner=app_owner, priority=10)
        OperatorFactory.register_owner_priority(owner=plugin_owner, priority=50)

        class AppOperator(AbstractOperator):
            short_name = "mock_op"
            owner = app_owner

            @staticmethod
            def is_available():
                return True

            def transform(self, table, *, file_name: str = ""):
                return table, {}

        class PluginOperator(AbstractOperator):
            short_name = "mock_op"
            owner = plugin_owner

            @staticmethod
            def is_available():
                return True

            def transform(self, table, *, file_name: str = ""):
                return table, {}

        try:
            # app (10) overrides OSS (200)
            should_override, new_p, existing_p = OperatorFactory.resolve_operator_by_priority(
                new_operator=AppOperator,
                existing_operator=MockOSSOperator,
                default_owner=DocpipeConstants.OWNER_DOCPIPE,
            )
            assert should_override is True
            assert new_p == 10
            assert existing_p == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_DOCPIPE]

            # app (10) overrides plugin (50)
            should_override, new_p, existing_p = OperatorFactory.resolve_operator_by_priority(
                new_operator=AppOperator,
                existing_operator=PluginOperator,
                default_owner=DocpipeConstants.OWNER_DOCPIPE,
            )
            assert should_override is True
            assert new_p == 10
            assert existing_p == 50

            # plugin (50) overrides custom (100)
            should_override, new_p, existing_p = OperatorFactory.resolve_operator_by_priority(
                new_operator=PluginOperator,
                existing_operator=MockCustomOperator,
                default_owner=DocpipeConstants.OWNER_DOCPIPE,
            )
            assert should_override is True
            assert new_p == 50
            assert existing_p == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_CUSTOM]

            # plugin (50) cannot override app (10)
            should_override, new_p, existing_p = OperatorFactory.resolve_operator_by_priority(
                new_operator=PluginOperator,
                existing_operator=AppOperator,
                default_owner=DocpipeConstants.OWNER_DOCPIPE,
            )
            assert should_override is False
            assert new_p == 50
            assert existing_p == 10

            # custom (100) cannot override plugin (50)
            should_override, new_p, existing_p = OperatorFactory.resolve_operator_by_priority(
                new_operator=MockCustomOperator,
                existing_operator=PluginOperator,
                default_owner=DocpipeConstants.OWNER_DOCPIPE,
            )
            assert should_override is False
            assert new_p == DocpipeConstants.OPERATOR_PRIORITY_MAP[DocpipeConstants.OWNER_CUSTOM]
            assert existing_p == 50
        finally:
            DocpipeConstants.OPERATOR_PRIORITY_MAP.pop(app_owner, None)
            DocpipeConstants.OPERATOR_PRIORITY_MAP.pop(plugin_owner, None)

    def test_register_owner_priority_overwrites_existing(self):
        """Test that re-registering an owner updates its priority."""
        owner = "test_overwrite_owner"
        try:
            OperatorFactory.register_owner_priority(owner=owner, priority=90)
            assert DocpipeConstants.OPERATOR_PRIORITY_MAP[owner] == 90

            OperatorFactory.register_owner_priority(owner=owner, priority=30)
            assert DocpipeConstants.OPERATOR_PRIORITY_MAP[owner] == 30
        finally:
            DocpipeConstants.OPERATOR_PRIORITY_MAP.pop(owner, None)
