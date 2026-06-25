"""OpenTelemetry telemetry service for distributed tracing.

This module provides a singleton telemetry service that:
- Lazily initializes OpenTelemetry SDK when enabled
- Provides zero overhead when disabled
- Handles missing OTEL dependencies gracefully
- Integrates with existing transaction ID infrastructure
"""

import os
from dataclasses import dataclass
from typing import Any

from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

# Default telemetry configuration constants
DEFAULT_TELEMETRY_ENABLED = False
DEFAULT_OTEL_SERVICE_NAME = "docling-pipelines"
DEFAULT_OTEL_ENDPOINT = "http://localhost:4317"
DEFAULT_OTEL_SERVICE_VERSION = "0.1.0"
DEFAULT_OTEL_DEPLOYMENT_ENVIRONMENT = "development"


@dataclass
class TelemetryConfig:
    """Configuration for telemetry service.

    Attributes:
        enabled: Whether telemetry is enabled
        service_name: Name of the service in traces
        otlp_endpoint: OTLP endpoint URL
        service_version: Version of the service
        deployment_environment: Deployment environment name
        otlp_headers: Optional headers for OTLP exporter (e.g., authentication)
    """

    enabled: bool = DEFAULT_TELEMETRY_ENABLED
    service_name: str = DEFAULT_OTEL_SERVICE_NAME
    otlp_endpoint: str = DEFAULT_OTEL_ENDPOINT
    service_version: str = DEFAULT_OTEL_SERVICE_VERSION
    deployment_environment: str = DEFAULT_OTEL_DEPLOYMENT_ENVIRONMENT
    otlp_headers: dict[str, str] | None = None

    @classmethod
    def from_environment(cls) -> "TelemetryConfig":
        """Load configuration from environment variables.

        Returns:
            TelemetryConfig instance with values from environment
        """
        enabled_str = os.getenv("TELEMETRY_ENABLED", "false").lower()
        enabled = enabled_str in ("true", "1", "yes", "on")

        # Parse OTEL headers if provided
        headers = None
        headers_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
        if headers_str:
            headers = cls._parse_headers(headers_str)

        return cls(
            enabled=enabled,
            service_name=os.getenv("OTEL_SERVICE_NAME", DEFAULT_OTEL_SERVICE_NAME),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTEL_ENDPOINT),
            service_version=os.getenv("OTEL_SERVICE_VERSION", DEFAULT_OTEL_SERVICE_VERSION),
            deployment_environment=os.getenv("OTEL_DEPLOYMENT_ENVIRONMENT", DEFAULT_OTEL_DEPLOYMENT_ENVIRONMENT),
            otlp_headers=headers,
        )

    @staticmethod
    def _parse_headers(headers_str: str) -> dict[str, str]:
        """Parse OTEL headers from environment variable format.

        Supports formats:
        - key1=value1,key2=value2
        - key1=value1 key2=value2
        - Authorization=Basic <token> (keeps value together)

        Args:
            headers_str: Headers string from environment variable

        Returns:
            Dictionary of header key-value pairs with lowercase keys (gRPC requirement)
        """
        headers = {}
        # Split by comma first to handle multiple headers
        pairs = headers_str.split(",")
        for pair in pairs:
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                # URL decode the value if needed
                value = value.replace("%20", " ")
                # gRPC metadata keys must be lowercase
                headers[key.strip().lower()] = value.strip()
        return headers


class TelemetryService:
    """Singleton service for OpenTelemetry tracing.

    This service provides:
    - Lazy initialization of OTEL SDK
    - Span creation and management
    - Exception recording
    - Zero overhead when disabled
    - Graceful handling of missing dependencies
    """

    _instance: "TelemetryService | None" = None
    _initialized: bool
    _enabled: bool
    _tracer: Any
    _tracer_provider: Any

    def __new__(cls) -> "TelemetryService":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._enabled = False
            cls._instance._tracer = None
            cls._instance._tracer_provider = None
        return cls._instance

    def __init__(self):
        """Initialize telemetry service (called on every get_telemetry_service call)."""
        # Initialization happens in initialize() method
        pass

    def initialize(self, *, config: TelemetryConfig | None = None) -> None:
        """Initialize OpenTelemetry SDK with configuration.

        Args:
            config: Telemetry configuration. If None, loads from environment.
        """
        if self._initialized:
            logger.debug("Telemetry service already initialized")
            return

        if config is None:
            config = TelemetryConfig.from_environment()

        self._enabled = config.enabled

        if not self._enabled:
            logger.info("Telemetry is disabled")
            self._initialized = True
            return

        try:
            # Import OTEL dependencies only when enabled
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,  # type: ignore[import-not-found]
            )
            from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
            from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
            from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import-not-found]

            # Create resource with service metadata
            resource = Resource.create(
                {
                    "service.name": config.service_name,
                    "service.version": config.service_version,
                    "deployment.environment": config.deployment_environment,
                }
            )

            # Create tracer provider
            self._tracer_provider = TracerProvider(resource=resource)

            # Determine if endpoint uses secure connection
            is_secure = config.otlp_endpoint.startswith("https://")

            # Create OTLP exporter with proper configuration
            if config.otlp_headers:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=config.otlp_endpoint,
                    insecure=not is_secure,
                    headers=config.otlp_headers,
                )
            else:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=config.otlp_endpoint,
                    insecure=not is_secure,
                )

            # Add batch span processor for efficient export
            span_processor = BatchSpanProcessor(otlp_exporter)
            self._tracer_provider.add_span_processor(span_processor)

            # Set global tracer provider
            trace.set_tracer_provider(self._tracer_provider)

            # Get tracer instance
            self._tracer = trace.get_tracer(__name__)

            logger.info(
                "Telemetry initialized successfully",
                extra={
                    "service_name": config.service_name,
                    "otlp_endpoint": config.otlp_endpoint,
                    "deployment_environment": config.deployment_environment,
                    "secure_connection": is_secure,
                    "headers_configured": bool(config.otlp_headers),
                },
            )

        except ImportError as e:
            logger.warning(
                "OpenTelemetry dependencies not installed. Install with: uv pip install -e '.[telemetry]'",
                extra={"error": str(e)},
            )
            self._enabled = False
        except Exception as e:
            logger.error(
                "Failed to initialize telemetry",
                extra={"error": str(e)},
                exc_info=True,
            )
            self._enabled = False

        self._initialized = True

    def start_span(self, name: str, *, attributes: dict[str, Any] | None = None):
        """Start a new span.

        Auto-initializes telemetry on first use if not already initialized.

        Args:
            name: Name of the span
            attributes: Optional attributes to add to the span

        Returns:
            Span object if enabled, None otherwise
        """
        # Auto-initialize on first use
        if not self._initialized:
            self.initialize()

        if not self._enabled or self._tracer is None:
            return None

        try:
            span = self._tracer.start_span(name)

            # Add attributes if provided
            if attributes:
                for key, value in attributes.items():
                    if value is not None:
                        span.set_attribute(key, value)

            return span
        except Exception as e:
            logger.debug(f"Failed to start span: {e}")
            return None

    def end_span(self, span) -> None:
        """End a span.

        Args:
            span: Span to end (can be None)
        """
        if span is None or not self._enabled:
            return

        try:
            span.end()
        except Exception as e:
            logger.debug(f"Failed to end span: {e}")

    def set_span_attribute(self, key: str, value: Any, *, span=None) -> None:
        """Set an attribute on a span.

        Args:
            key: Attribute key
            value: Attribute value
            span: Span to set attribute on. If None, uses current span.
        """
        if not self._enabled:
            return

        try:
            if span is None:
                from opentelemetry import trace

                span = trace.get_current_span()

            if span is not None and value is not None:
                span.set_attribute(key, value)
        except Exception as e:
            logger.debug(f"Failed to set span attribute: {e}")

    def record_exception(self, exception: Exception, *, span=None) -> None:
        """Record an exception in a span.

        Args:
            exception: Exception to record
            span: Span to record exception in. If None, uses current span.
        """
        if not self._enabled:
            return

        try:
            if span is None:
                from opentelemetry import trace

                span = trace.get_current_span()

            if span is not None:
                span.record_exception(exception)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))
        except Exception as e:
            logger.debug(f"Failed to record exception: {e}")

    def get_current_span(self):
        """Get the current active span.

        Returns:
            Current span if enabled, None otherwise
        """
        if not self._enabled:
            return None

        try:
            from opentelemetry import trace

            return trace.get_current_span()
        except Exception as e:
            logger.debug(f"Failed to get current span: {e}")
            return None

    def shutdown(self) -> None:
        """Shutdown telemetry service and flush pending spans."""
        if not self._enabled or self._tracer_provider is None:
            return

        try:
            logger.info("Shutting down telemetry service")
            self._tracer_provider.shutdown()
        except Exception as e:
            logger.error(f"Failed to shutdown telemetry: {e}")

    @property
    def is_enabled(self) -> bool:
        """Check if telemetry is enabled.

        Returns:
            True if telemetry is enabled, False otherwise
        """
        return self._enabled


# Global singleton instance
_telemetry_service: TelemetryService | None = None


def get_telemetry_service() -> TelemetryService:
    """Get the global telemetry service instance.

    Returns:
        TelemetryService singleton instance
    """
    global _telemetry_service
    if _telemetry_service is None:
        _telemetry_service = TelemetryService()
    return _telemetry_service
