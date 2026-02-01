import pytest

from egregora.orchestration.error_boundary import DefaultErrorBoundary


def test_handle_journal_error_raises_fatal():
    boundary = DefaultErrorBoundary()
    with pytest.raises(ValueError, match="Journal error"):
        boundary.handle_journal_error(ValueError("Journal error"), context="test")


def test_handle_writer_error_raises_fatal():
    boundary = DefaultErrorBoundary()
    with pytest.raises(ValueError, match="Writer error"):
        boundary.handle_writer_error(ValueError("Writer error"), context="test")


def test_handle_enrichment_error_does_not_raise():
    boundary = DefaultErrorBoundary()
    # Should warn but not raise
    boundary.handle_enrichment_error(ValueError("Enrichment error"), context="test")


def test_handle_profile_error_does_not_raise():
    boundary = DefaultErrorBoundary()
    boundary.handle_profile_error(ValueError("Profile error"), context="test")


def test_handle_command_error_does_not_raise():
    boundary = DefaultErrorBoundary()
    boundary.handle_command_error(ValueError("Command error"), context="test")


def test_handle_output_error_raises_fatal():
    boundary = DefaultErrorBoundary()
    with pytest.raises(ValueError, match="Output error"):
        boundary.handle_output_error(ValueError("Output error"), context="test")
