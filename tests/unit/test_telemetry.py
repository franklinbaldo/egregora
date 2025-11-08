"""Tests for OpenTelemetry telemetry module.

Tests verify that OTEL integration:
1. Only activates when EGREGORA_OTEL=1
2. Handles missing dependencies gracefully
3. Returns no-op tracer when disabled
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def _has_otel_packages() -> bool:
    """Check if OpenTelemetry packages are installed."""
    try:
        import opentelemetry.trace  # noqa: F401
        import opentelemetry.sdk.trace  # noqa: F401
        return True
    except ImportError:
        return False


class TestOtelConfiguration:
    """Test OTEL configuration and lazy initialization."""

    def test_otel_disabled_by_default(self):
        """OTEL is disabled when EGREGORA_OTEL is not set."""
        from egregora.utils.telemetry import is_otel_enabled
        
        with patch.dict(os.environ, {}, clear=True):
            assert not is_otel_enabled()

    def test_otel_enabled_when_env_set(self):
        """OTEL is enabled when EGREGORA_OTEL=1."""
        from egregora.utils.telemetry import is_otel_enabled
        
        with patch.dict(os.environ, {"EGREGORA_OTEL": "1"}):
            assert is_otel_enabled()

    def test_otel_disabled_when_env_wrong_value(self):
        """OTEL is disabled when EGREGORA_OTEL != '1'."""
        from egregora.utils.telemetry import is_otel_enabled
        
        with patch.dict(os.environ, {"EGREGORA_OTEL": "true"}):
            assert not is_otel_enabled()
        
        with patch.dict(os.environ, {"EGREGORA_OTEL": "0"}):
            assert not is_otel_enabled()

    def test_configure_otel_returns_none_when_disabled(self):
        """configure_otel() returns None when OTEL disabled."""
        from egregora.utils.telemetry import configure_otel
        
        with patch.dict(os.environ, {}, clear=True):
            provider = configure_otel()
            assert provider is None

    def test_get_tracer_returns_tracer_when_disabled(self):
        """get_tracer() returns a tracer even when OTEL disabled (no-op)."""
        from egregora.utils.telemetry import get_tracer
        
        with patch.dict(os.environ, {}, clear=True):
            tracer = get_tracer("test")
            assert tracer is not None

    def test_shutdown_otel_no_error_when_not_configured(self):
        """shutdown_otel() doesn't error when OTEL not configured."""
        from egregora.utils.telemetry import shutdown_otel
        
        # Should not raise
        shutdown_otel()


class TestOtelIntegration:
    """Integration tests for OTEL (require opentelemetry packages)."""

    @pytest.mark.skipif(
        not _has_otel_packages(),
        reason="OpenTelemetry packages not installed"
    )
    def test_configure_otel_with_console_exporter(self):
        """configure_otel() sets up console exporter when no OTLP endpoint."""
        from egregora.utils.telemetry import configure_otel
        
        with patch.dict(os.environ, {"EGREGORA_OTEL": "1"}, clear=True):
            provider = configure_otel()
            assert provider is not None

    @pytest.mark.skipif(
        not _has_otel_packages(),
        reason="OpenTelemetry packages not installed"
    )
    def test_get_tracer_returns_real_tracer_when_enabled(self):
        """get_tracer() returns real OTEL tracer when enabled."""
        from egregora.utils.telemetry import get_tracer
        
        with patch.dict(os.environ, {"EGREGORA_OTEL": "1"}, clear=True):
            tracer = get_tracer("test.module")
            assert tracer is not None
            
            # Tracer should have start_as_current_span method
            assert hasattr(tracer, "start_as_current_span")

    @pytest.mark.skipif(
        not _has_otel_packages(),
        reason="OpenTelemetry packages not installed"
    )
    def test_tracer_creates_spans(self):
        """Tracer creates valid spans when OTEL enabled."""
        from egregora.utils.telemetry import get_tracer
        
        with patch.dict(os.environ, {"EGREGORA_OTEL": "1"}, clear=True):
            tracer = get_tracer("test.spans")
            
            # Should not raise
            with tracer.start_as_current_span("test_span") as span:
                assert span is not None
