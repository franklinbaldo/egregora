from unittest.mock import MagicMock, patch

import pytest

from egregora.orchestration.error_boundary import (
    DefaultErrorBoundary,
    ErrorBoundary,
    FailureStrategy,
)


def test_handle_journal_error_raises_fatal():
    """Verify journal errors raise (FATAL strategy)."""
    boundary = DefaultErrorBoundary()
    with pytest.raises(ValueError, match="Journal error"):
        boundary.handle_journal_error(ValueError("Journal error"), context="test")


def test_handle_journal_error_logs_critical():
    """Verify journal errors log at critical level."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.logger") as mock_logger:
        with pytest.raises(ValueError):
            boundary.handle_journal_error(ValueError("Journal error"), context="test_context")

        mock_logger.critical.assert_called_once()
        call_args = mock_logger.critical.call_args[0][0]
        assert "Journal error" in call_args
        assert "test_context" in call_args


def test_handle_journal_error_prints_to_console():
    """Verify journal errors print to console."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.console.print") as mock_print:
        with pytest.raises(ValueError):
            boundary.handle_journal_error(ValueError("Journal error"), context="test")

        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Critical Journal Error" in call_args
        assert "Journal error" in call_args


def test_handle_writer_error_raises_fatal():
    """Verify writer errors raise (FATAL strategy)."""
    boundary = DefaultErrorBoundary()
    with pytest.raises(ValueError, match="Writer error"):
        boundary.handle_writer_error(ValueError("Writer error"), context="test")


def test_handle_writer_error_logs_error():
    """Verify writer errors log at error level."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.logger") as mock_logger:
        with pytest.raises(ValueError):
            boundary.handle_writer_error(ValueError("Writer error"), context="writer_test")

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "Writer error" in call_args
        assert "writer_test" in call_args


def test_handle_writer_error_prints_to_console():
    """Verify writer errors print to console."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.console.print") as mock_print:
        with pytest.raises(ValueError):
            boundary.handle_writer_error(ValueError("Writer error"), context="test")

        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Writer Error" in call_args


def test_handle_enrichment_error_does_not_raise():
    """Verify enrichment errors don't raise (WARN strategy)."""
    boundary = DefaultErrorBoundary()
    # Should warn but not raise
    boundary.handle_enrichment_error(ValueError("Enrichment error"), context="test")


def test_handle_enrichment_error_logs_warning():
    """Verify enrichment errors log at warning level."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.logger") as mock_logger:
        boundary.handle_enrichment_error(ValueError("Enrichment error"), context="enrich_test")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "Enrichment failed" in call_args
        assert "enrich_test" in call_args


def test_handle_enrichment_error_prints_to_console():
    """Verify enrichment errors print warning to console."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.console.print") as mock_print:
        boundary.handle_enrichment_error(ValueError("Enrichment error"), context="test")

        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Enrichment warning" in call_args


def test_handle_profile_error_does_not_raise():
    """Verify profile errors don't raise (WARN strategy)."""
    boundary = DefaultErrorBoundary()
    boundary.handle_profile_error(ValueError("Profile error"), context="test")


def test_handle_profile_error_logs_warning():
    """Verify profile errors log at warning level."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.logger") as mock_logger:
        boundary.handle_profile_error(ValueError("Profile error"), context="profile_test")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "Profile generation failed" in call_args
        assert "profile_test" in call_args


def test_handle_profile_error_prints_to_console():
    """Verify profile errors print warning to console."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.console.print") as mock_print:
        boundary.handle_profile_error(ValueError("Profile error"), context="test")

        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Profile warning" in call_args


def test_handle_command_error_does_not_raise():
    """Verify command errors don't raise (WARN strategy)."""
    boundary = DefaultErrorBoundary()
    boundary.handle_command_error(ValueError("Command error"), context="test")


def test_handle_command_error_logs_warning():
    """Verify command errors log at warning level."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.logger") as mock_logger:
        boundary.handle_command_error(ValueError("Command error"), context="command_test")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "Command processing failed" in call_args
        assert "command_test" in call_args


def test_handle_command_error_prints_to_console():
    """Verify command errors print warning to console."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.console.print") as mock_print:
        boundary.handle_command_error(ValueError("Command error"), context="test")

        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Command warning" in call_args


def test_handle_output_error_raises_fatal():
    """Verify output errors raise (FATAL strategy)."""
    boundary = DefaultErrorBoundary()
    with pytest.raises(ValueError, match="Output error"):
        boundary.handle_output_error(ValueError("Output error"), context="test")


def test_handle_output_error_logs_critical():
    """Verify output errors log at critical level."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.logger") as mock_logger:
        with pytest.raises(ValueError):
            boundary.handle_output_error(ValueError("Output error"), context="output_test")

        mock_logger.critical.assert_called_once()
        call_args = mock_logger.critical.call_args[0][0]
        assert "Output persistence failed" in call_args
        assert "output_test" in call_args


def test_handle_output_error_prints_to_console():
    """Verify output errors print to console."""
    boundary = DefaultErrorBoundary()
    with patch("egregora.orchestration.error_boundary.console.print") as mock_print:
        with pytest.raises(ValueError):
            boundary.handle_output_error(ValueError("Output error"), context="test")

        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Output Error" in call_args


def test_failure_strategy_enum_values():
    """Verify FailureStrategy enum has expected values."""
    assert FailureStrategy.FATAL.value == "fatal"
    assert FailureStrategy.WARN.value == "warn"
    assert FailureStrategy.SILENT.value == "silent"
    assert FailureStrategy.RETRY.value == "retry"


def test_failure_strategy_enum_members():
    """Verify FailureStrategy has all expected members."""
    strategies = [s.name for s in FailureStrategy]
    assert "FATAL" in strategies
    assert "WARN" in strategies
    assert "SILENT" in strategies
    assert "RETRY" in strategies


def test_error_boundary_protocol_signature():
    """Verify ErrorBoundary protocol has expected methods."""
    # Check that the protocol defines the expected methods
    assert hasattr(ErrorBoundary, "handle_journal_error")
    assert hasattr(ErrorBoundary, "handle_enrichment_error")
    assert hasattr(ErrorBoundary, "handle_writer_error")
    assert hasattr(ErrorBoundary, "handle_profile_error")
    assert hasattr(ErrorBoundary, "handle_command_error")
    assert hasattr(ErrorBoundary, "handle_output_error")


def test_default_error_boundary_implements_protocol():
    """Verify DefaultErrorBoundary implements all protocol methods."""
    boundary = DefaultErrorBoundary()

    # Check all methods exist and are callable
    assert callable(boundary.handle_journal_error)
    assert callable(boundary.handle_enrichment_error)
    assert callable(boundary.handle_writer_error)
    assert callable(boundary.handle_profile_error)
    assert callable(boundary.handle_command_error)
    assert callable(boundary.handle_output_error)


def test_error_boundary_protocol_can_be_mocked():
    """Verify ErrorBoundary protocol can be implemented by custom classes."""

    class CustomBoundary:
        def handle_journal_error(self, e: Exception, context: str = "") -> None:
            pass

        def handle_enrichment_error(self, e: Exception, context: str = "") -> None:
            pass

        def handle_writer_error(self, e: Exception, context: str = "") -> None:
            pass

        def handle_profile_error(self, e: Exception, context: str = "") -> None:
            pass

        def handle_command_error(self, e: Exception, context: str = "") -> None:
            pass

        def handle_output_error(self, e: Exception, context: str = "") -> None:
            pass

    custom = CustomBoundary()
    # Should not raise - duck typing works with Protocol
    custom.handle_journal_error(ValueError("test"))


def test_context_parameter_default_empty_string():
    """Verify context parameter defaults to empty string."""
    boundary = DefaultErrorBoundary()

    # These should work without context parameter
    boundary.handle_enrichment_error(ValueError("test"))
    boundary.handle_profile_error(ValueError("test"))
    boundary.handle_command_error(ValueError("test"))


def test_all_error_types_propagate_correctly():
    """Verify different exception types are propagated correctly."""
    boundary = DefaultErrorBoundary()

    # Test with different exception types
    with pytest.raises(RuntimeError):
        boundary.handle_journal_error(RuntimeError("runtime error"))

    with pytest.raises(IOError):
        boundary.handle_writer_error(IOError("io error"))

    with pytest.raises(ConnectionError):
        boundary.handle_output_error(ConnectionError("connection error"))


def test_multiple_calls_independent():
    """Verify multiple error handler calls don't interfere with each other."""
    boundary = DefaultErrorBoundary()

    # Non-fatal errors should be independent
    boundary.handle_enrichment_error(ValueError("error 1"))
    boundary.handle_profile_error(ValueError("error 2"))
    boundary.handle_command_error(ValueError("error 3"))

    # All three should have been handled without raising


def test_empty_context_string_handled():
    """Verify empty context string is handled gracefully."""
    boundary = DefaultErrorBoundary()

    with patch("egregora.orchestration.error_boundary.logger") as mock_logger:
        boundary.handle_enrichment_error(ValueError("test"), context="")

        # Should still log, even with empty context
        mock_logger.warning.assert_called_once()
