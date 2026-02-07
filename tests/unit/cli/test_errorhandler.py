from unittest.mock import patch

import pytest
import typer

from egregora.agents.exceptions import EnrichmentError, ReaderError
from egregora.cli.errorhandler import handle_cli_errors
from egregora.config.exceptions import (
    ApiKeyNotFoundError,
    ConfigError,
    InvalidConfigurationValueError,
    SiteStructureError,
)
from egregora.input_adapters.exceptions import UnknownAdapterError
from egregora.orchestration.exceptions import (
    ApiKeyInvalidError,
    CommandAnnouncementError,
    OutputSinkError,
    ProfileGenerationError,
)


def test_handle_cli_errors_api_key_not_found():
    """Verify ApiKeyNotFoundError is handled with exit code 1."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "TEST_ENV_VAR"
                raise ApiKeyNotFoundError(msg)

        assert excinfo.value.exit_code == 1
        assert mock_print.called
        # Verify some part of the message
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("API Key Missing" in arg for arg in args)
        assert any("GOOGLE_API_KEY" in arg for arg in args)


def test_handle_cli_errors_api_key_invalid():
    """Verify ApiKeyInvalidError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Invalid Key"
                raise ApiKeyInvalidError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("API Key Invalid" in arg for arg in args)


def test_handle_cli_errors_api_key_invalid_with_validation_errors():
    """Verify ApiKeyInvalidError with validation_errors displays them."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                exc = ApiKeyInvalidError("Invalid Key")
                exc.validation_errors = ["Error 1: Bad format", "Error 2: Too short"]
                raise exc

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("API Key Invalid" in arg for arg in args)
        # Check that validation errors are printed
        assert any("Error 1: Bad format" in arg for arg in args)
        assert any("Error 2: Too short" in arg for arg in args)


def test_handle_cli_errors_debug_mode_re_raises():
    """Verify debug mode re-raises specific exceptions."""
    with pytest.raises(ApiKeyNotFoundError):
        with handle_cli_errors(debug=True):
            msg = "TEST_ENV_VAR"
            raise ApiKeyNotFoundError(msg)


def test_handle_cli_errors_unknown_adapter():
    """Verify UnknownAdapterError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "bad_source"
                raise UnknownAdapterError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("Unknown Source Adapter" in arg for arg in args)


def test_handle_cli_errors_invalid_configuration_value():
    """Verify InvalidConfigurationValueError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Invalid config value"
                raise InvalidConfigurationValueError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("Invalid Configuration" in arg for arg in args)


def test_handle_cli_errors_site_structure_error():
    """Verify SiteStructureError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Site structure problem"
                raise SiteStructureError(path="/test/site", reason=msg)

        assert excinfo.value.exit_code == 1
        # Check that print was called
        assert mock_print.called
        # Collect all print calls as strings
        all_calls = " ".join([str(call) for call in mock_print.call_args_list])
        # Check for error message (with or without emoji)
        assert "Site Structure" in all_calls or "structure problem" in all_calls


def test_handle_cli_errors_command_announcement_error():
    """Verify CommandAnnouncementError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Command failed"
                raise CommandAnnouncementError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("Processing Error" in arg for arg in args)


def test_handle_cli_errors_profile_generation_error():
    """Verify ProfileGenerationError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Profile generation failed"
                raise ProfileGenerationError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("Processing Error" in arg for arg in args)


def test_handle_cli_errors_output_sink_error():
    """Verify OutputSinkError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Output sink failed"
                raise OutputSinkError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("Processing Error" in arg for arg in args)


def test_handle_cli_errors_enrichment_error():
    """Verify EnrichmentError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Enrichment failed"
                raise EnrichmentError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("Enrichment Failed" in arg for arg in args)


def test_handle_cli_errors_reader_error():
    """Verify ReaderError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Reader failed"
                raise ReaderError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("Reader Error" in arg for arg in args)


def test_handle_cli_errors_config_error():
    """Verify ConfigError is handled."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Config error"
                raise ConfigError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("Configuration Error" in arg for arg in args)


def test_handle_cli_errors_keyboard_interrupt_re_raises():
    """Verify KeyboardInterrupt is re-raised without handling."""
    with pytest.raises(KeyboardInterrupt):
        with handle_cli_errors(debug=False):
            raise KeyboardInterrupt


def test_handle_cli_errors_system_exit_re_raises():
    """Verify SystemExit is re-raised without handling."""
    with pytest.raises(SystemExit):
        with handle_cli_errors(debug=False):
            raise SystemExit(0)


def test_handle_cli_errors_unexpected_exception():
    """Verify generic exception handling."""
    with patch("egregora.cli.errorhandler.console.print") as mock_print:
        with pytest.raises(typer.Exit) as excinfo:
            with handle_cli_errors(debug=False):
                msg = "Oops"
                raise ValueError(msg)

        assert excinfo.value.exit_code == 1
        args = [str(arg) for call in mock_print.call_args_list for arg in call[0]]
        assert any("An unexpected error occurred" in arg for arg in args)
        assert any("--debug" in arg for arg in args)


def test_handle_cli_errors_unexpected_exception_debug():
    """Verify generic exception handling in debug mode prints trace and exits."""
    with patch("egregora.cli.errorhandler.console.print_exception") as mock_print_exc:
        with pytest.raises(typer.Exit):
            with handle_cli_errors(debug=True):
                msg = "Oops"
                raise ValueError(msg)

        assert mock_print_exc.called
        mock_print_exc.assert_called_once_with(show_locals=False)


def test_handle_cli_errors_no_error_yields_normally():
    """Verify context manager works normally when no exception occurs."""
    with handle_cli_errors(debug=False):
        # Should not raise anything
        x = 1 + 1
        assert x == 2


def test_handle_cli_errors_enrichment_error_debug_mode():
    """Verify EnrichmentError in debug mode re-raises."""
    with pytest.raises(EnrichmentError):
        with handle_cli_errors(debug=True):
            msg = "Enrichment failed"
            raise EnrichmentError(msg)


def test_handle_cli_errors_config_error_debug_mode():
    """Verify ConfigError in debug mode re-raises."""
    with pytest.raises(ConfigError):
        with handle_cli_errors(debug=True):
            msg = "Config error"
            raise ConfigError(msg)


def test_handle_cli_errors_site_structure_error_debug_mode():
    """Verify SiteStructureError in debug mode re-raises."""
    with pytest.raises(SiteStructureError, match="Site structure error"):
        with handle_cli_errors(debug=True):
            msg = "Site structure error"
            raise SiteStructureError(path="/test/site", reason=msg)
