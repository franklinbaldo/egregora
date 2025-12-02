"""Integration tests for utility CLI commands (doctor).

These tests verify that the doctor command works correctly,
using CliRunner from typer.testing to simulate CLI invocations.
"""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from egregora.cli.main import app

# Create a CLI runner for testing
runner = CliRunner()


class TestDoctorCommand:
    """Tests for 'egregora doctor' command."""

    def test_doctor_command_basic(self):
        """Test basic doctor command without flags."""
        result = runner.invoke(app, ["doctor"])

        # Doctor command should complete (may exit with 0 or 1 depending on environment)
        assert result.exit_code in (0, 1), f"Doctor failed unexpectedly: {result.stdout}"

        # Should contain diagnostic output
        assert "diagnostics" in result.stdout.lower() or "check" in result.stdout.lower()

    def test_doctor_command_verbose(self):
        """Test doctor command with --verbose flag."""
        result = runner.invoke(app, ["doctor", "--verbose"])

        assert result.exit_code in (0, 1)
        # Verbose output should contain more information
        assert "python" in result.stdout.lower() or "version" in result.stdout.lower()

    def test_doctor_command_verbose_short_flag(self):
        """Test doctor command with -v short flag."""
        result = runner.invoke(app, ["doctor", "-v"])

        assert result.exit_code in (0, 1)
        assert "python" in result.stdout.lower() or "version" in result.stdout.lower()

    def test_doctor_command_shows_summary(self):
        """Test that doctor command displays a summary."""
        result = runner.invoke(app, ["doctor"])

        # Should show summary with counts
        assert (
            "summary" in result.stdout.lower()
            or "ok" in result.stdout.lower()
            or "error" in result.stdout.lower()
        )

    def test_doctor_command_checks_python_version(self):
        """Test that doctor checks Python version."""
        result = runner.invoke(app, ["doctor"])

        assert "python" in result.stdout.lower()

    def test_doctor_command_checks_packages(self):
        """Test that doctor checks required packages."""
        result = runner.invoke(app, ["doctor"])

        # Should mention packages or dependencies
        output_lower = result.stdout.lower()
        assert (
            "package" in output_lower
            or "ibis" in output_lower
            or "duckdb" in output_lower
            or "error" in output_lower
        )

    def test_doctor_exit_code_on_success(self):
        """Test doctor exits with 0 when all checks pass (mocked)."""
        # This test mocks the diagnostics to all return OK
        with patch("egregora.diagnostics.run_diagnostics") as mock_diagnostics:
            from egregora.diagnostics import DiagnosticResult, HealthStatus

            mock_diagnostics.return_value = [
                DiagnosticResult(check="Python Version", status=HealthStatus.OK, message="Python 3.12.0"),
                DiagnosticResult(
                    check="Required Packages", status=HealthStatus.OK, message="All packages installed"
                ),
            ]

            result = runner.invoke(app, ["doctor"])
            assert result.exit_code == 0

    def test_doctor_exit_code_on_error(self):
        """Test doctor exits with 1 when errors are found (mocked)."""
        with patch("egregora.diagnostics.run_diagnostics") as mock_diagnostics:
            from egregora.diagnostics import DiagnosticResult, HealthStatus

            mock_diagnostics.return_value = [
                DiagnosticResult(
                    check="API Key", status=HealthStatus.ERROR, message="GOOGLE_API_KEY not set"
                ),
            ]

            result = runner.invoke(app, ["doctor"])
            assert result.exit_code == 1

    def test_doctor_continues_on_warnings(self):
        """Test doctor exits with 0 even when warnings are found."""
        with patch("egregora.diagnostics.run_diagnostics") as mock_diagnostics:
            from egregora.diagnostics import DiagnosticResult, HealthStatus

            mock_diagnostics.return_value = [
                DiagnosticResult(
                    check="Some Warning", status=HealthStatus.WARNING, message="Generic warning message"
                ),
            ]

            result = runner.invoke(app, ["doctor"])
            assert result.exit_code == 0
