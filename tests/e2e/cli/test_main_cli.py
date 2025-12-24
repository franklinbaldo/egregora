"""Tests for the main CLI application."""

import re

from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def test_cli_help():
    """Test that the main CLI entrypoint runs and shows help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Strip ANSI escape codes for reliable assertion
    clean_output = _strip_ansi(result.stdout)
    assert "Usage: egregora [OPTIONS] COMMAND [ARGS]..." in clean_output
