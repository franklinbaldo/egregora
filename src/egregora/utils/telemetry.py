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

    # Determine export destination
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if otlp_endpoint:
        # Production: Export to OTLP collector (requires opentelemetry-exporter-otlp)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            logger.info(f"OpenTelemetry: Exporting to OTLP endpoint {otlp_endpoint}")
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
        # Development: Export to console
        logger.info("OpenTelemetry: Exporting to console (set OTEL_EXPORTER_OTLP_ENDPOINT for OTLP)")
        console_exporter = ConsoleSpanExporter()
        _provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Set as global provider
    trace.set_tracer_provider(_provider)

    logger.info("OpenTelemetry configured successfully")
    return _provider


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


# Note: All telemetry exports removed from __all__ - OpenTelemetry integration never activated
# Functions remain available for direct import if needed in the future
__all__: list[str] = []
