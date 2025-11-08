"""OpenTelemetry integration for observability (opt-in).

This module provides lightweight OpenTelemetry integration for:
1. Distributed tracing (pipeline stages, LLM calls)
2. Metrics (counters, gauges, histograms)
3. Logs (structured logging with trace context)

Usage:
    # Enable telemetry (opt-in)
    export EGREGORA_OTEL=1
    export OTEL_SERVICE_NAME="egregora"
    export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"

    # In code
    from egregora.utils.telemetry import configure_otel, get_tracer

    # Configure once at startup
    configure_otel()

    # Use tracer
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("enrichment") as span:
        span.set_attribute("rows", 100)
        result = enrich_data()

Environment Variables:
    EGREGORA_OTEL: Enable telemetry (0=disabled, 1=enabled)
    OTEL_SERVICE_NAME: Service name for traces (default: "egregora")
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (default: http://localhost:4318)
    OTEL_EXPORTER_OTLP_PROTOCOL: Protocol (default: http/protobuf)
"""

import os
import sys
from contextlib import contextmanager
from typing import Any, Iterator

# Lazy imports to avoid requiring OpenTelemetry dependencies
_OTEL_ENABLED = os.getenv("EGREGORA_OTEL", "0") == "1"
_OTEL_CONFIGURED = False


def is_telemetry_enabled() -> bool:
    """Check if telemetry is enabled via environment variable.

    Returns:
        True if EGREGORA_OTEL=1, False otherwise
    """
    return _OTEL_ENABLED


def configure_otel() -> None:
    """Configure OpenTelemetry (opt-in).

    This function:
    1. Checks if EGREGORA_OTEL=1
    2. Imports OpenTelemetry libraries (lazy)
    3. Configures OTLP exporter
    4. Sets up TracerProvider
    5. Registers shutdown hook

    Raises:
        ImportError: If OpenTelemetry packages not installed
        RuntimeError: If configuration fails

    Example:
        >>> # Enable telemetry
        >>> os.environ["EGREGORA_OTEL"] = "1"
        >>> configure_otel()
        >>> tracer = get_tracer(__name__)
    """
    global _OTEL_CONFIGURED

    # Skip if already configured
    if _OTEL_CONFIGURED:
        return

    # Skip if telemetry disabled
    if not _OTEL_ENABLED:
        return

    try:
        # Lazy imports
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Create resource (service name, version, etc.)
        service_name = os.getenv("OTEL_SERVICE_NAME", "egregora")
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": "1.0.0",  # FIXME: Read from package metadata
            }
        )

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Configure OTLP exporter
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")

        # Add batch span processor (buffers spans for efficiency)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Register shutdown hook
        import atexit

        def shutdown_telemetry():
            provider.shutdown()

        atexit.register(shutdown_telemetry)

        _OTEL_CONFIGURED = True

    except ImportError as e:
        # OpenTelemetry not installed
        print(
            f"Warning: EGREGORA_OTEL=1 but OpenTelemetry packages not installed: {e}",
            file=sys.stderr,
        )
        print(
            "Install with: uv add opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http",
            file=sys.stderr,
        )
        # Don't fail - just disable telemetry
        return

    except Exception as e:
        # Configuration error
        print(
            f"Warning: Failed to configure OpenTelemetry: {e}",
            file=sys.stderr,
        )
        return


def get_tracer(name: str):
    """Get OpenTelemetry tracer.

    Args:
        name: Tracer name (typically __name__)

    Returns:
        Tracer instance (or no-op tracer if telemetry disabled)

    Example:
        >>> tracer = get_tracer(__name__)
        >>> with tracer.start_as_current_span("my_operation"):
        ...     do_work()
    """
    if not _OTEL_ENABLED:
        # Return no-op tracer (doesn't fail if telemetry disabled)
        from opentelemetry import trace

        return trace.get_tracer(name)

    # Ensure configured
    configure_otel()

    # Return real tracer
    from opentelemetry import trace

    return trace.get_tracer(name)


@contextmanager
def traced_operation(
    operation_name: str,
    *,
    attributes: dict[str, Any] | None = None,
    tracer_name: str = "egregora",
) -> Iterator[Any]:
    """Context manager for tracing an operation.

    Args:
        operation_name: Name of the operation (span name)
        attributes: Optional attributes to set on span
        tracer_name: Tracer name (default: "egregora")

    Yields:
        Span object (can set additional attributes)

    Example:
        >>> with traced_operation("enrich_urls", attributes={"url_count": 10}):
        ...     enrich_urls(table)
    """
    if not _OTEL_ENABLED:
        # No-op if telemetry disabled
        yield None
        return

    tracer = get_tracer(tracer_name)
    with tracer.start_as_current_span(operation_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def get_current_trace_id() -> str | None:
    """Get current OpenTelemetry trace ID.

    Returns:
        Trace ID as hex string, or None if no active span

    Example:
        >>> with traced_operation("my_op"):
        ...     trace_id = get_current_trace_id()
        ...     print(f"Trace ID: {trace_id}")
    """
    if not _OTEL_ENABLED:
        return None

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is None or not span.is_recording():
            return None

        context = span.get_span_context()
        if not context.is_valid:
            return None

        # Convert trace_id to hex string
        return format(context.trace_id, "032x")

    except ImportError:
        return None


# ==============================================================================
# Convenience decorators
# ==============================================================================


def traced(operation_name: str | None = None, **default_attributes: Any):
    """Decorator for tracing a function.

    Args:
        operation_name: Span name (defaults to function name)
        **default_attributes: Default attributes to set on span

    Example:
        >>> @traced("process_data", stage="enrichment")
        ... def process_table(table):
        ...     return table.mutate(processed=True)
    """

    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = func.__name__

        def wrapper(*args, **kwargs):
            if not _OTEL_ENABLED:
                # Skip tracing if disabled
                return func(*args, **kwargs)

            with traced_operation(operation_name, attributes=default_attributes) as span:
                # Execute function
                result = func(*args, **kwargs)

                # Optionally set result attributes
                if span and hasattr(result, "__len__"):
                    try:
                        span.set_attribute("result.length", len(result))
                    except TypeError:
                        pass

                return result

        return wrapper

    return decorator
