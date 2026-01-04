from pathlib import Path

from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()


def test_doctor_command_shows_checks():
    """Test that the `doctor` command runs and shows the expected checks."""
    # Create a dummy config file to satisfy the doctor check
    config_file = Path(".egregora.toml")
    config_file.write_text("[rag]\nenabled = true")

    try:
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0

        # Check for some of the key diagnostic strings in the output
        assert "Python Version" in result.stdout
        assert "Required Packages" in result.stdout
        assert "API Key" in result.stdout
        assert "DuckDB ZipFS Extension" in result.stdout
        assert "Git" in result.stdout
        assert "Cache Directory" in result.stdout
        assert "Egregora Config" in result.stdout
        assert "Source Adapters" in result.stdout
    finally:
        # Clean up the dummy config file
        config_file.unlink()
