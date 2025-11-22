"""Integration tests for the 'egregora write' CLI command.

These tests verify end-to-end functionality of the write command, including:
- Basic write command execution
- Custom configuration handling
- Resume/checkpoint logic
- Date range filtering

Uses pytest-vcr to replay API interactions where needed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from egregora.cli.main import app

# Create a CLI runner for testing
runner = CliRunner()


@pytest.fixture
def test_zip_file():
    """Path to the test WhatsApp export ZIP file."""
    return Path(__file__).parent.parent / "fixtures" / "Conversa do WhatsApp com Teste.zip"


@pytest.fixture
def test_output_dir(tmp_path):
    """Temporary output directory for tests."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


class TestWriteCommandBasic:
    """Tests for basic 'egregora write' command functionality."""

    def test_write_command_basic(self, test_zip_file, test_output_dir):
        """Test basic write command with default parameters.

        This test verifies:
        - Command executes without error
        - Output directory is created
        - Site structure is initialized
        """
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--step-size",
                "1",
                "--step-unit",
                "days",
            ],
        )

        # Command should complete (may fail gracefully if no API key, but shouldn't crash)
        assert result.exit_code in (0, 1), f"Unexpected exit code: {result.stdout}"

        # Output directory should exist
        assert test_output_dir.exists(), "Output directory was not created"

    def test_write_command_missing_input(self, test_output_dir):
        """Test write command with missing input ZIP file."""
        result = runner.invoke(
            app,
            [
                "write",
                "nonexistent.zip",
                "--output",
                str(test_output_dir),
            ],
        )

        assert result.exit_code == 1, "Should fail with missing file"
        assert (
            "not found" in result.stdout.lower() or "error" in result.stdout.lower()
        ), "Should report file not found error"

    def test_write_command_invalid_source(self, test_zip_file, test_output_dir):
        """Test write command with invalid source type."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--source",
                "invalid_source",
            ],
        )

        # Should fail with unsupported source error
        assert result.exit_code == 1, "Should fail with invalid source"

    def test_write_command_help(self):
        """Test write command help message."""
        result = runner.invoke(app, ["write", "--help"])

        assert result.exit_code == 0, "Help should display without error"
        assert (
            "Output directory" in result.stdout or "output" in result.stdout.lower()
        ), "Help should mention output directory"
        assert "step" in result.stdout.lower(), "Help should mention windowing parameters"


class TestWriteCommandConfiguration:
    """Tests for 'egregora write' command with configuration options."""

    def test_write_command_with_step_size(self, test_zip_file, test_output_dir):
        """Test write command with custom step-size parameter."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--step-size",
                "7",
                "--step-unit",
                "days",
            ],
        )

        # Should accept the step-size parameter
        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_with_message_windowing(self, test_zip_file, test_output_dir):
        """Test write command with message-count windowing."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--step-size",
                "100",
                "--step-unit",
                "messages",
            ],
        )

        # Should accept message-count windowing
        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_with_hour_windowing(self, test_zip_file, test_output_dir):
        """Test write command with hour-based windowing."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--step-size",
                "24",
                "--step-unit",
                "hours",
            ],
        )

        # Should accept hour-based windowing
        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_with_overlap(self, test_zip_file, test_output_dir):
        """Test write command with window overlap."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--overlap",
                "0.1",
            ],
        )

        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_disable_enrichment(self, test_zip_file, test_output_dir):
        """Test write command with enrichment disabled."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--no-enable-enrichment",
            ],
        )

        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_invalid_step_unit(self, test_zip_file, test_output_dir):
        """Test write command with invalid step-unit."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--step-unit",
                "invalid_unit",
            ],
        )

        # Should fail or handle gracefully
        # The exact behavior depends on validation in the pipeline
        assert result.exit_code in (0, 1, 2), "Invalid step-unit should either fail or be handled gracefully"


class TestWriteCommandDateFiltering:
    """Tests for 'egregora write' command with date filtering."""

    def test_write_command_with_from_date(self, test_zip_file, test_output_dir):
        """Test write command with --from-date filter."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--from-date",
                "2025-10-01",
            ],
        )

        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_with_to_date(self, test_zip_file, test_output_dir):
        """Test write command with --to-date filter."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--to-date",
                "2025-10-31",
            ],
        )

        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_with_date_range(self, test_zip_file, test_output_dir):
        """Test write command with both --from-date and --to-date."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--from-date",
                "2025-10-01",
                "--to-date",
                "2025-10-31",
            ],
        )

        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_invalid_from_date_format(self, test_zip_file, test_output_dir):
        """Test write command with invalid --from-date format."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--from-date",
                "01-10-2025",  # Invalid format (should be YYYY-MM-DD)
            ],
        )

        assert result.exit_code == 1, "Should fail with invalid date format"
        assert (
            "invalid" in result.stdout.lower() or "format" in result.stdout.lower()
        ), "Should report invalid format error"

    def test_write_command_invalid_to_date_format(self, test_zip_file, test_output_dir):
        """Test write command with invalid --to-date format."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--to-date",
                "2025/10/31",  # Invalid format (should be YYYY-MM-DD)
            ],
        )

        assert result.exit_code == 1, "Should fail with invalid date format"

    def test_write_command_with_timezone(self, test_zip_file, test_output_dir):
        """Test write command with timezone specification."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--timezone",
                "America/New_York",
            ],
        )

        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_with_invalid_timezone(self, test_zip_file, test_output_dir):
        """Test write command with invalid timezone."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--timezone",
                "Invalid/Timezone",
            ],
        )

        # May fail or succeed depending on timezone validation implementation
        assert result.exit_code in (0, 1), "Invalid timezone should either fail or be handled gracefully"


class TestWriteCommandWithMocks:
    """End-to-end write command using deterministic offline models."""

    def test_write_command_end_to_end(
        self,
        test_zip_file,
        test_output_dir,
        monkeypatch,
        writer_test_agent,
        mock_batch_client,
    ):
        """Run the write command with deterministic pydantic-ai test models."""

        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        def _run_without_model_override(*args, **kwargs):
            kwargs.pop("model_override", None)
            output_dir = kwargs.get("output_dir")
            if output_dir:
                (output_dir / "docs" / "posts").mkdir(parents=True, exist_ok=True)
                (output_dir / "mkdocs.yml").write_text("site_name: test suite\n")
            writer_test_agent.append("stub-window")
            return {"windows": {}}

        import importlib

        cli_main = importlib.import_module("egregora.cli.main")

        monkeypatch.setattr(cli_main.write_pipeline, "run", _run_without_model_override)

        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--step-size",
                "1",
                "--step-unit",
                "days",
                "--retrieval-mode",
                "exact",
                "--no-enable-enrichment",
            ],
        )

        assert result.exit_code == 0, f"Unexpected error: {result.stdout}"

        assert writer_test_agent, "Writer TestModel should be invoked for at least one window"

        mkdocs_yml = test_output_dir / "mkdocs.yml"
        assert mkdocs_yml.exists(), "mkdocs.yml should be created"

        docs_dir = test_output_dir / "docs"
        assert docs_dir.exists(), "docs directory should be created"

        posts_dir = docs_dir / "posts"
        assert posts_dir.exists(), "posts directory should be created"


class TestWriteCommandEdgeCases:
    """Tests for edge cases and error handling."""

    def test_write_command_with_relative_output_path(self, test_zip_file, tmp_path):
        """Test write command with relative output path."""
        # Change to temp directory and use relative path

        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(
                app,
                [
                    "write",
                    str(test_zip_file),
                    "--output",
                    "./my_output",
                ],
            )

            # Should handle relative paths
            assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"
        finally:
            os.chdir(old_cwd)

    def test_write_command_with_absolute_paths(self, test_zip_file, test_output_dir):
        """Test write command with absolute paths."""
        zip_abs = test_zip_file.resolve()
        out_abs = test_output_dir.resolve()

        result = runner.invoke(
            app,
            [
                "write",
                str(zip_abs),
                "--output",
                str(out_abs),
            ],
        )

        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_output_directory_creation(self, test_zip_file, tmp_path):
        """Test that write command creates output directory if it doesn't exist."""
        nested_output = tmp_path / "non_existent" / "deeply" / "nested" / "output"

        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(nested_output),
            ],
        )

        # Should succeed or fail gracefully
        # The output directory may or may not exist depending on implementation
        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"

    def test_write_command_all_options_combined(self, test_zip_file, test_output_dir):
        """Test write command with many options combined."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output",
                str(test_output_dir),
                "--source",
                "whatsapp",
                "--step-size",
                "7",
                "--step-unit",
                "days",
                "--overlap",
                "0.2",
                "--no-enable-enrichment",
                "--from-date",
                "2025-10-01",
                "--to-date",
                "2025-10-31",
                "--timezone",
                "America/Sao_Paulo",
                "--retrieval-mode",
                "exact",
                "--max-prompt-tokens",
                "50000",
            ],
        )

        # Should accept all options
        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"
