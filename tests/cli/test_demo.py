from unittest.mock import patch

from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()


@patch("egregora.cli.main._run_offline_demo")
def test_demo_command_offline_mode(mock_run_offline_demo):
    """Test that the demo command runs in offline mode when no API key is set."""
    with patch.dict("os.environ", {}, clear=True):
        result = runner.invoke(app, ["demo"])
        assert result.exit_code == 0
        mock_run_offline_demo.assert_called_once()


@patch("egregora.cli.main.run_cli_flow")
def test_demo_command_online_mode(mock_run_cli_flow):
    """Test that the demo command runs in online mode when an API key is set."""
    with patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"}, clear=True):
        result = runner.invoke(app, ["demo"])
        assert result.exit_code == 0
        mock_run_cli_flow.assert_called_once()
