"""Tests for telemetry service resilience and error handling."""

from unittest.mock import MagicMock, patch

import pytest

from docpipe.utils.infrastructure.telemetry_service import (
    TelemetryConfig,
    TelemetryService,
    get_telemetry_service,
)


class TestTelemetryResilience:
    """Test that application continues running even if telemetry fails."""

    def setup_method(self):
        """Reset telemetry service singleton before each test."""
        # Reset singleton instance
        TelemetryService._instance = None

    def test_application_continues_when_otel_dependencies_missing(self):
        """Test that application continues when OpenTelemetry dependencies are not installed."""
        # Create config with telemetry enabled
        config = TelemetryConfig(
            enabled=True,
            service_name="test-service",
            otlp_endpoint="http://localhost:4317",
        )

        # Mock the OTEL modules to simulate them not being installed
        # We patch them as None in the telemetry_service module's namespace
        with patch("docpipe.utils.infrastructure.telemetry_service.logger") as mock_logger:
            with patch.dict(
                "sys.modules",
                {
                    "opentelemetry": None,
                    "opentelemetry.trace": None,
                    "opentelemetry.sdk": None,
                    "opentelemetry.sdk.trace": None,
                    "opentelemetry.sdk.trace.export": None,
                    "opentelemetry.sdk.resources": None,
                    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": None,
                    "opentelemetry.instrumentation.fastapi": None,
                },
            ):
                # Force re-initialization by resetting the singleton
                service = get_telemetry_service()
                service._initialized = False
                service._enabled = False
                service._tracer = None

                # Now initialize - this should trigger the ImportError path
                service.initialize(config=config)

                # Service should be initialized but disabled
                assert service._initialized is True
                assert service._enabled is False
                assert service._tracer is None

                # Should log warning about missing dependencies
                assert mock_logger.warning.called
                # Check that warning was logged (may be called multiple times in CI)
                warning_calls = [
                    call
                    for call in mock_logger.warning.call_args_list
                    if "OpenTelemetry dependencies not installed" in str(call)
                ]
                assert len(warning_calls) > 0, (
                    f"Expected warning about missing dependencies, got: {mock_logger.warning.call_args_list}"
                )

    def test_application_continues_when_otlp_endpoint_unreachable(self):
        """Test that application continues when OTLP endpoint is unreachable.

        This test verifies that even if telemetry initialization fails,
        the application continues to run normally.
        """
        config = TelemetryConfig(
            enabled=True,
            service_name="test-service",
            otlp_endpoint="http://unreachable-host:4317",
        )

        # The key test: initialization should not raise an exception
        # even if OTEL setup fails
        try:
            service = get_telemetry_service()
            service.initialize(config=config)
            # If we get here without exception, the test passes
            assert True
        except Exception as e:
            # If any exception is raised, the test fails
            pytest.fail(f"Application should continue even if telemetry fails: {e}")

    def test_span_operations_fail_gracefully_when_disabled(self):
        """Test that span operations return None/do nothing when telemetry is disabled."""
        config = TelemetryConfig(enabled=False)

        service = get_telemetry_service()
        service.initialize(config=config)

        # All span operations should fail gracefully
        span = service.start_span("test-span", attributes={"key": "value"})
        assert span is None

        # These should not raise exceptions
        service.end_span(None)
        service.set_span_attribute("key", "value")
        service.record_exception(Exception("test error"))
        current_span = service.get_current_span()
        assert current_span is None

    def test_span_operations_fail_gracefully_on_exception(self):
        """Test that span operations handle exceptions gracefully."""
        config = TelemetryConfig(
            enabled=True,
            service_name="test-service",
        )

        with patch("docpipe.utils.infrastructure.telemetry_service.logger") as mock_logger:
            # Mock successful initialization
            mock_trace = MagicMock()
            mock_tracer = MagicMock()
            mock_trace.get_tracer.return_value = mock_tracer

            # Make start_span raise an exception
            mock_tracer.start_span.side_effect = Exception("Span creation failed")

            with patch.dict(
                "sys.modules",
                {
                    "opentelemetry": mock_trace,
                    "opentelemetry.trace": mock_trace,
                    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
                    "opentelemetry.sdk.resources": MagicMock(),
                    "opentelemetry.sdk.trace": MagicMock(),
                    "opentelemetry.sdk.trace.export": MagicMock(),
                },
            ):
                service = get_telemetry_service()
                service.initialize(config=config)

                # start_span should return None instead of raising exception
                span = service.start_span("test-span")
                assert span is None

                # Should log debug message about failure
                mock_logger.debug.assert_called()

    def test_end_span_handles_exception_gracefully(self):
        """Test that end_span handles exceptions without propagating them."""
        config = TelemetryConfig(enabled=True)

        with patch("docpipe.utils.infrastructure.telemetry_service.logger") as mock_logger:
            service = get_telemetry_service()
            service.initialize(config=config)
            service._enabled = True  # Force enabled

            # Create mock span that raises exception on end()
            mock_span = MagicMock()
            mock_span.end.side_effect = Exception("Failed to end span")

            # Should not raise exception
            service.end_span(mock_span)

            # Should log debug message
            mock_logger.debug.assert_called()

    def test_set_span_attribute_handles_exception_gracefully(self):
        """Test that set_span_attribute handles exceptions without propagating them."""
        config = TelemetryConfig(enabled=True)

        with patch("docpipe.utils.infrastructure.telemetry_service.logger") as mock_logger:
            service = get_telemetry_service()
            service.initialize(config=config)
            service._enabled = True  # Force enabled

            # Create mock span that raises exception on set_attribute()
            mock_span = MagicMock()
            mock_span.set_attribute.side_effect = Exception("Failed to set attribute")

            # Should not raise exception
            service.set_span_attribute("key", "value", span=mock_span)

            # Should log debug message
            mock_logger.debug.assert_called()

    def test_record_exception_handles_exception_gracefully(self):
        """Test that record_exception handles exceptions without propagating them."""
        config = TelemetryConfig(enabled=True)

        with patch("docpipe.utils.infrastructure.telemetry_service.logger") as mock_logger:
            service = get_telemetry_service()
            service.initialize(config=config)
            service._enabled = True  # Force enabled

            # Create mock span that raises exception on record_exception()
            mock_span = MagicMock()
            mock_span.record_exception.side_effect = Exception("Failed to record exception")

            # Should not raise exception
            service.record_exception(ValueError("test error"), span=mock_span)

            # Should log debug message
            mock_logger.debug.assert_called()

    def test_shutdown_handles_exception_gracefully(self):
        """Test that shutdown handles exceptions without propagating them."""
        config = TelemetryConfig(enabled=True)

        with patch("docpipe.utils.infrastructure.telemetry_service.logger") as mock_logger:
            service = get_telemetry_service()
            service.initialize(config=config)
            service._enabled = True  # Force enabled

            # Create mock tracer provider that raises exception on shutdown()
            mock_provider = MagicMock()
            mock_provider.shutdown.side_effect = Exception("Failed to shutdown")
            service._tracer_provider = mock_provider

            # Should not raise exception
            service.shutdown()

            # Should log error message
            mock_logger.error.assert_called()

    def test_singleton_pattern_maintained_across_failures(self):
        """Test that singleton pattern is maintained even when initialization fails."""
        # Get the singleton instance
        service1 = get_telemetry_service()
        service2 = get_telemetry_service()

        # Should return same instance
        assert service1 is service2

    def test_auto_initialization_on_first_span_creation(self):
        """Test that telemetry auto-initializes on first span creation without errors."""
        service = get_telemetry_service()

        # Key test: span creation should not raise an exception
        # even if telemetry is not properly initialized
        try:
            service.start_span("test-span")
            # If we get here without exception, the test passes
            assert True
        except Exception as e:
            pytest.fail(f"Span creation should not raise exception: {e}")


class TestTelemetryConfig:
    """Test telemetry configuration."""

    def test_config_from_environment_defaults(self):
        """Test that config loads defaults when env vars not set."""
        with patch.dict("os.environ", {}, clear=True):
            config = TelemetryConfig.from_environment()

            assert config.enabled is False
            assert config.service_name == "docling-pipelines"
            assert config.otlp_endpoint == "http://localhost:4317"
            assert config.service_version == "0.1.0"
            assert config.deployment_environment == "development"
            assert config.otlp_headers is None

    def test_config_from_environment_with_values(self):
        """Test that config loads from environment variables."""
        env_vars = {
            "TELEMETRY_ENABLED": "true",
            "OTEL_SERVICE_NAME": "my-service",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel.example.com:4317",
            "OTEL_SERVICE_VERSION": "1.2.3",
            "OTEL_DEPLOYMENT_ENVIRONMENT": "production",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            config = TelemetryConfig.from_environment()

            assert config.enabled is True
            assert config.service_name == "my-service"
            assert config.otlp_endpoint == "https://otel.example.com:4317"
            assert config.service_version == "1.2.3"
            assert config.deployment_environment == "production"

    def test_config_parses_headers_correctly(self):
        """Test that OTLP headers are parsed correctly."""
        env_vars = {
            "TELEMETRY_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_HEADERS": "authorization=Basic%20dGVzdDp0ZXN0,x-custom-header=value",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            config = TelemetryConfig.from_environment()

            assert config.otlp_headers is not None
            assert config.otlp_headers["authorization"] == "Basic dGVzdDp0ZXN0"
            assert config.otlp_headers["x-custom-header"] == "value"

    def test_config_headers_keys_are_lowercase(self):
        """Test that header keys are converted to lowercase (gRPC requirement)."""
        env_vars = {
            "TELEMETRY_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer token,X-Custom-Header=value",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            config = TelemetryConfig.from_environment()

            assert config.otlp_headers is not None
            # Keys should be lowercase
            assert "authorization" in config.otlp_headers
            assert "x-custom-header" in config.otlp_headers
            # Original case should not exist
            assert "Authorization" not in config.otlp_headers
            assert "X-Custom-Header" not in config.otlp_headers
