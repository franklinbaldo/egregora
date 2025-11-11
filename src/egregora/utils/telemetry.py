"""OpenTelemetry instrumentation (optional, off by default).

Provides distributed tracing for Egregora pipeline stages when enabled
via EGREGORA_OTEL=1 environment variable.

This is a minimal bootstrap that:
- Only activates when explicitly enabled
- Exports to console by default (for debugging)
- Can be configured for OTLP export (production observability)

Usage:
    export EGREGORA_OTEL=1
    egregora process export.zip

Dependencies (optional):
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Tracer

logger = logging.getLogger(__name__)

# Global tracer instance (lazy-initialized)
_tracer: Tracer | None = None
_provider: TracerProvider | None = None


def is_otel_enabled() -> bool:
    """Check if OpenTelemetry is enabled via environment variable.

    Returns:
        True if EGREGORA_OTEL=1, False otherwise

    """
    return os.getenv("EGREGORA_OTEL") == "1"


def configure_otel() -> TracerProvider | None:
    """Configure OpenTelemetry if EGREGORA_OTEL=1.

    Exporter priority (first available wins):
    1. Logfire (if LOGFIRE_TOKEN set) - Pydantic's observability platform
    2. OTLP (if OTEL_EXPORTER_OTLP_ENDPOINT set) - Generic OTLP collector
    3. Console (default) - Debug output to stdout

    Returns:
        TracerProvider if enabled and dependencies available, None otherwise

    Example:
        >>> provider = configure_otel()
        >>> if provider:
        ...     tracer = provider.get_tracer("egregora.pipeline")

    """
    global _provider

    if not is_otel_enabled():
        return None

    if _provider is not None:
        return _provider

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError:
        logger.warning(
            "OpenTelemetry requested (EGREGORA_OTEL=1) but dependencies not installed. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk"
        )
        return None

    _provider = TracerProvider()

    # Determine export destination (priority order)
    logfire_token = os.getenv("LOGFIRE_TOKEN")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if logfire_token:
        # Priority 1: Logfire (Pydantic's OTEL-compatible observability)
        try:
            import logfire

            logger.info("OpenTelemetry: Integrating with Logfire (OTEL-compatible)")
            logfire.configure(token=logfire_token, send_to_logfire=True)

            # Logfire automatically integrates with OTEL when configure() is called
            # The provider is already set up by logfire.configure()
            # We just need to ensure our tracer uses the Logfire-configured provider
            _provider = trace.get_tracer_provider()  # type: ignore[assignment]

            logger.info("OpenTelemetry: Logfire exporter configured")
        except ImportError:
            logger.warning(
                "LOGFIRE_TOKEN set but logfire package not installed. "
                "Install with: pip install logfire. Falling back to OTLP/Console."
            )
            # Fall through to OTLP/Console
            _configure_fallback_exporter(_provider, otlp_endpoint)
    elif otlp_endpoint:
        # Priority 2: OTLP collector (generic observability backend)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            logger.info("OpenTelemetry: Exporting to OTLP endpoint %s", otlp_endpoint)
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            _provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except ImportError:
            logger.warning(
                "OTLP endpoint configured but opentelemetry-exporter-otlp not installed. "
                "Falling back to console exporter. Install with: pip install opentelemetry-exporter-otlp"
            )
            console_exporter = ConsoleSpanExporter()
            _provider.add_span_processor(BatchSpanProcessor(console_exporter))
    else:
        # Priority 3: Console (development/debugging)
        logger.info("OpenTelemetry: Exporting to console (set LOGFIRE_TOKEN or OTEL_EXPORTER_OTLP_ENDPOINT)")
        console_exporter = ConsoleSpanExporter()
        _provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Set as global provider (unless Logfire already did)
    if not logfire_token:
        trace.set_tracer_provider(_provider)

    logger.info("OpenTelemetry configured successfully")
    return _provider


def _configure_fallback_exporter(provider: TracerProvider, otlp_endpoint: str | None) -> None:
    """Configure fallback exporter when Logfire is unavailable.

    Args:
        provider: TracerProvider to configure
        otlp_endpoint: OTLP endpoint URL (optional)

    """
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            logger.info("OpenTelemetry: Exporting to OTLP endpoint %s", otlp_endpoint)
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except ImportError:
            logger.warning(
                "OTLP endpoint configured but opentelemetry-exporter-otlp not installed. "
                "Falling back to console exporter."
            )
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))
    else:
        logger.info("OpenTelemetry: Exporting to console")
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))


def get_tracer(name: str = "egregora") -> Tracer:
    """Get OpenTelemetry tracer (lazy-initialized).

    Args:
        name: Tracer name (typically module or service name)

    Returns:
        Tracer instance (may be no-op if OTEL disabled or unavailable)

    Example:
        >>> tracer = get_tracer("egregora.pipeline")
        >>> with tracer.start_as_current_span("parse_whatsapp"):
        ...     parse_export(path)

    """
    global _tracer

    if _tracer is None:
        provider = configure_otel()

        if provider is None:
            # Return no-op tracer if disabled or unavailable
            try:
                from opentelemetry import trace

                _tracer = trace.get_tracer(name)
            except ImportError:
                # Even OpenTelemetry API not available - create dummy tracer
                from types import SimpleNamespace

                _tracer = SimpleNamespace(start_as_current_span=_no_op_span)  # type: ignore[assignment]
        else:
            from opentelemetry import trace

            _tracer = trace.get_tracer(name)

    return _tracer


def _no_op_span(name: str, **_kwargs: Any):
    """No-op context manager when OTEL is disabled."""
    from contextlib import nullcontext

    return nullcontext()


def get_current_trace_id() -> str | None:
    """Get current OpenTelemetry trace ID from active span context.

    Used for linking runs database records to OTEL traces.

    Returns:
        Trace ID as hex string (e.g., "abc123..."), or None if no active span

    Example:
        >>> from opentelemetry import trace
        >>> tracer = get_tracer("egregora.pipeline")
        >>> with tracer.start_as_current_span("my_operation"):
        ...     trace_id = get_current_trace_id()
        ...     record_run(..., trace_id=trace_id)

    """
    if not is_otel_enabled():
        return None

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            # Format trace ID as 32-character hex string
            return format(span.get_span_context().trace_id, "032x")
    except Exception:
        # Gracefully handle any OTEL errors
        return None
    else:
        return None


def shutdown_otel() -> None:
    """Shutdown OpenTelemetry and flush pending spans.

    Call this on graceful shutdown to ensure all spans are exported.

    Example:
        >>> try:
        ...     run_pipeline()
        ... finally:
        ...     shutdown_otel()

    """
    global _provider

    if _provider is not None:
        logger.info("Shutting down OpenTelemetry...")
        _provider.shutdown()
        _provider = None


__all__ = [
    "configure_otel",
    "get_current_trace_id",
    "get_tracer",
    "is_otel_enabled",
    "shutdown_otel",
]
