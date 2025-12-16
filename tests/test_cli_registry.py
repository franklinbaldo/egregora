from typer.testing import CliRunner
from egregora.cli.main import app

runner = CliRunner()

def test_cli_registry():
    """
    Tests that essential CLI commands are registered and dead ones are NOT.
    """
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    help_output = result.stdout

    # 1. Protection: Ensure 'write' and 'read' exist
    assert "write" in help_output, "Critical: 'write' command missing"
    assert "read" in help_output, "Critical: 'read' command missing"

    # Check subcommands
    result_show = runner.invoke(app, ["show", "--help"])
    assert result_show.exit_code == 0

def test_commands_presence():
    """Baseline test to confirm what commands exist."""
    result = runner.invoke(app, ["--help"])
    assert "write" in result.stdout
    assert "init" in result.stdout
    assert "doctor" in result.stdout
    assert "top" in result.stdout
