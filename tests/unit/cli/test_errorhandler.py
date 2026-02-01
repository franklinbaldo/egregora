from unittest.mock import patch

import pytest
import typer

from egregora.cli.errorhandler import handle_cli_errors
from egregora.config.exceptions import ApiKeyNotFoundError
from egregora.input_adapters.exceptions import UnknownAdapterError
from egregora.orchestration.exceptions import ApiKeyInvalidError


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


def test_handle_cli_errors_unexpected_exception_debug():
    """Verify generic exception handling in debug mode prints trace and exits."""
    with patch("egregora.cli.errorhandler.console.print_exception") as mock_print_exc:
        with pytest.raises(typer.Exit):
            with handle_cli_errors(debug=True):
                msg = "Oops"
                raise ValueError(msg)

        assert mock_print_exc.called
