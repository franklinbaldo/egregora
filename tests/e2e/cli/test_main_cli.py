"""Tests for the main CLI application."""

from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()


def test_cli_help():
    """Test that the main CLI entrypoint runs and shows help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage: egregora [OPTIONS] COMMAND [ARGS]..." in result.stdout
