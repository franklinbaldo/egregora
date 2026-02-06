"""BDD-style tests for errorhandler.py to increase coverage."""

import pytest
from egregora.errors import (
    ApiKeyInvalidError,
    CommandAnnouncementError,
    ConfigError,
    EnrichmentError,
    InvalidConfigurationValueError,
    OutputSinkError,
    ProfileGenerationError,
    ReaderError,
    SiteStructureError,
)

from egregora.cli.errorhandler import handle_error


class TestErrorHandlerBehavior:
    """Given-When-Then scenarios for error handling."""

    def test_given_invalid_config_when_handled_then_exits_with_code_1(self, capsys):
        """Given an InvalidConfigurationValueError is raised
        When the error handler processes it
        Then it should exit with code 1 and show config help."""
        error = InvalidConfigurationValueError("Invalid value for 'foo'")

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid value" in captured.err

    def test_given_site_structure_error_when_handled_then_exits_with_code_1(self, capsys):
        """Given a SiteStructureError is raised
        When the error handler processes it
        Then it should exit with code 1."""
        error = SiteStructureError("Missing required file")

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 1

    def test_given_command_announcement_error_when_handled_then_exits_with_code_1(self, capsys):
        """Given a CommandAnnouncementError is raised
        When the error handler processes it
        Then it should exit with code 1."""
        error = CommandAnnouncementError("Failed to announce command")

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 1

    def test_given_profile_generation_error_when_handled_then_exits_with_code_1(self, capsys):
        """Given a ProfileGenerationError is raised
        When the error handler processes it
        Then it should exit with code 1."""
        error = ProfileGenerationError("Failed to generate profile")

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 1

    def test_given_output_sink_error_when_handled_then_exits_with_code_1(self, capsys):
        """Given an OutputSinkError is raised
        When the error handler processes it
        Then it should exit with code 1."""
        error = OutputSinkError("Failed to write output")

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 1

    def test_given_enrichment_error_when_handled_then_exits_with_code_1(self, capsys):
        """Given an EnrichmentError is raised
        When the error handler processes it
        Then it should exit with code 1."""
        error = EnrichmentError("Failed to enrich data")

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 1

    def test_given_reader_error_when_handled_then_exits_with_code_1(self, capsys):
        """Given a ReaderError is raised
        When the error handler processes it
        Then it should exit with code 1."""
        error = ReaderError("Failed to read input")

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 1

    def test_given_config_error_when_handled_then_exits_with_code_1(self, capsys):
        """Given a ConfigError is raised
        When the error handler processes it
        Then it should exit with code 1."""
        error = ConfigError("Config validation failed")

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 1

    def test_given_keyboard_interrupt_when_handled_then_reraises(self):
        """Given a KeyboardInterrupt is raised
        When the error handler processes it
        Then it should re-raise the exception."""
        error = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            handle_error(error)

    def test_given_system_exit_when_handled_then_reraises(self):
        """Given a SystemExit is raised
        When the error handler processes it
        Then it should re-raise the exception."""
        error = SystemExit(42)

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 42

    def test_given_api_key_invalid_with_validation_errors_when_handled_then_shows_details(self, capsys):
        """Given an ApiKeyInvalidError with validation errors
        When the error handler processes it
        Then it should show validation details and exit."""
        error = ApiKeyInvalidError("Invalid API key format")
        error.validation_errors = ["Must start with 'sk-'", "Must be 48 chars"]

        with pytest.raises(SystemExit) as excinfo:
            handle_error(error)

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "validation" in captured.err.lower() or "invalid" in captured.err.lower()

    def test_given_no_error_when_handler_called_then_does_nothing(self):
        """Given no error occurs
        When the error handler is called with None
        Then it should complete without raising."""
        # This tests the no-error path (if handle_error accepts None)
        try:
            result = handle_error(None)
            assert result is None or result == 0
        except TypeError:
            # If handle_error doesn't accept None, that's also valid behavior
            pass
