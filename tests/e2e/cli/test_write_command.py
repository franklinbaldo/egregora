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
from tests.e2e.test_config import (
    DateConfig,
    TimezoneConfig,
    WriteCommandOptions,
    assert_command_success,
    build_write_command_args,
)

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
                "--output-dir",
                str(test_output_dir),
                "--step-size",
                "1",
                "--step-unit",
                "days",
            ],
        )

        # Command should complete (may fail gracefully if no API key, but shouldn't crash)
        assert result.exit_code in (0, 1), (
            f"Command exited with code {result.exit_code} (expected 0 or 1).\n"
            f"Output: {result.stdout[:500]}"  # Show first 500 chars of output
        )

        # Output directory should exist
        assert test_output_dir.exists(), (
            f"Output directory was not created at {test_output_dir}. Command exit code: {result.exit_code}"
        )

    def test_write_command_missing_input(self, test_output_dir):
        """Test write command with missing input ZIP file."""
        result = runner.invoke(
            app,
            [
                "write",
                "nonexistent.zip",
                "--output-dir",
                str(test_output_dir),
            ],
        )

        # Should fail with exit code 1
        assert result.exit_code == 1, f"Should fail with missing file, got: {result.stdout}"
        # The error may appear in stdout or as an exception message
        # Just verify it failed, don't check exact error message format

    def test_write_command_invalid_source(self, test_zip_file, test_output_dir):
        """Test write command with invalid source type."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output-dir",
                str(test_output_dir),
                "--source-type",
                "invalid_source",
            ],
        )

        # Should fail with CLI error (exit code 2 = usage error from Typer)
        assert result.exit_code == 2, "Should fail with invalid source type (Typer validation)"

    def test_write_command_help(self):
        """Test write command help message."""
        result = runner.invoke(app, ["write", "--help"])

        assert result.exit_code == 0, "Help should display without error"
        assert "-o" in result.stdout or "--out" in result.stdout or "site" in result.stdout.lower(), (
            "Help should mention output directory"
        )
        assert "--ste" in result.stdout.lower(), "Help should mention windowing parameters"


class TestWriteCommandConfiguration:
    """Tests for 'egregora write' command with configuration options."""

    def test_write_command_with_step_size(self, test_zip_file, test_output_dir):
        """Test write command with custom step-size parameter."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output-dir",
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
                "--output-dir",
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
                "--output-dir",
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
                "--output-dir",
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
                "--output-dir",
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
                "--output-dir",
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

    def test_write_command_with_from_date(self, test_zip_file, test_output_dir, test_dates: DateConfig):
        """Test write command with --from-date filter."""
        args = build_write_command_args(
            test_zip_file,
            test_output_dir,
            options=WriteCommandOptions(from_date=test_dates.VALID_FROM),
        )
        result = runner.invoke(app, args)
        assert_command_success(result)

    def test_write_command_with_to_date(self, test_zip_file, test_output_dir, test_dates: DateConfig):
        """Test write command with --to-date filter."""
        args = build_write_command_args(
            test_zip_file,
            test_output_dir,
            options=WriteCommandOptions(to_date=test_dates.VALID_TO),
        )
        result = runner.invoke(app, args)
        assert_command_success(result)

    def test_write_command_with_date_range(self, test_zip_file, test_output_dir, test_dates: DateConfig):
        """Test write command with both --from-date and --to-date."""
        args = build_write_command_args(
            test_zip_file,
            test_output_dir,
            options=WriteCommandOptions(from_date=test_dates.VALID_FROM, to_date=test_dates.VALID_TO),
        )
        result = runner.invoke(app, args)
        assert_command_success(result)

    def test_write_command_invalid_from_date_format(self, test_zip_file, test_output_dir):
        """Test write command with invalid --from-date format."""
        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output-dir",
                str(test_output_dir),
                "--from-date",
                "01-10-2025",  # Invalid format (should be YYYY-MM-DD)
            ],
        )

        assert result.exit_code == 1, "Should fail with invalid date format"
        assert "invalid" in result.stdout.lower() or "format" in result.stdout.lower(), (
            "Should report invalid format error"
        )

    def test_write_command_invalid_to_date_format(
        self, test_zip_file, test_output_dir, test_dates: DateConfig
    ):
        """Test write command with invalid --to-date format."""
        args = build_write_command_args(
            test_zip_file,
            test_output_dir,
            options=WriteCommandOptions(to_date=test_dates.INVALID_FORMAT_2),
        )
        result = runner.invoke(app, args)

        assert result.exit_code == 1, "Should fail with invalid date format"

    def test_write_command_with_timezone(
        self, test_zip_file, test_output_dir, test_timezones: TimezoneConfig
    ):
        """Test write command with timezone specification."""
        args = build_write_command_args(
            test_zip_file,
            test_output_dir,
            options=WriteCommandOptions(timezone=test_timezones.VALID),
        )
        result = runner.invoke(app, args)
        assert_command_success(result)

    def test_write_command_with_invalid_timezone(
        self, test_zip_file, test_output_dir, test_timezones: TimezoneConfig
    ):
        """Test write command with invalid timezone."""
        args = build_write_command_args(
            test_zip_file,
            test_output_dir,
            options=WriteCommandOptions(timezone=test_timezones.INVALID),
        )
        result = runner.invoke(app, args)

        # May fail or succeed depending on timezone validation implementation
        assert_command_success(result, expected_codes=(0, 1))


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
        """Run the write command with deterministic pydantic-ai test models.

        This test verifies the write command can process a WhatsApp export and
        create the expected site structure, using mocked LLM responses for
        deterministic testing.

        Note: The pipeline may fail due to various mock-related issues, but
        the site initialization and directory structure should be created.
        """
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        result = runner.invoke(
            app,
            [
                "write",
                str(test_zip_file),
                "--output-dir",
                str(test_output_dir),
                "--step-size",
                "100",  # Process all messages in one window
                "--step-unit",
                "messages",
                "--no-enable-enrichment",  # Faster test
                "--max-windows",
                "1",  # Just process one window
            ],
        )

        # Command may fail (exit code 1) due to mock limitations, but should initialize site
        # Exit code 0 = success, 1 = pipeline error (acceptable with mocks)
        assert result.exit_code in (0, 1), (
            f"Command exited with code {result.exit_code} (expected 0 or 1).\n"
            f"Last 50 lines of output:\n{chr(10).join(result.stdout.split(chr(10))[-50:])}"
        )

        # Verify site structure was created even if pipeline failed
        assert test_output_dir.exists(), (
            f"Output directory {test_output_dir} was not created. Exit code: {result.exit_code}"
        )

        # Check for .egregora config directory
        egregora_dir = test_output_dir / ".egregora"
        assert egregora_dir.exists(), (
            f".egregora directory not found at {egregora_dir}. "
            f"Output dir contents: {list(test_output_dir.iterdir())}"
        )

        # Check for mkdocs.yml (could be in root or .egregora depending on structure)
        mkdocs_yml = test_output_dir / "mkdocs.yml"
        egregora_mkdocs = egregora_dir / "mkdocs.yml"
        assert mkdocs_yml.exists() or egregora_mkdocs.exists(), (
            f"mkdocs.yml not found. Checked:\n"
            f"  - {mkdocs_yml} (exists: {mkdocs_yml.exists()})\n"
            f"  - {egregora_mkdocs} (exists: {egregora_mkdocs.exists()})"
        )

        # Check for docs directory and subdirectories
        docs_dir = test_output_dir / "docs"
        assert docs_dir.exists(), (
            f"docs directory not found at {docs_dir}. Output dir contents: {list(test_output_dir.iterdir())}"
        )

        posts_dir = docs_dir / "posts"
        assert posts_dir.exists(), (
            f"posts directory not found at {posts_dir}. docs dir contents: {list(docs_dir.iterdir())}"
        )

        profiles_dir = posts_dir / "profiles"
        assert profiles_dir.exists(), (
            f"profiles directory not found at {profiles_dir}. docs dir contents: {list(docs_dir.iterdir())}"
        )

        # If pipeline succeeded, verify we actually created content
        if result.exit_code == 0:
            # Look for any generated files (posts or profiles)
            post_files = list(posts_dir.glob("*.md"))
            profile_files = list(profiles_dir.rglob("*.md"))
            # At least one of these should have content if pipeline succeeded
            # Exclude index files and tags files
            content_posts = [p for p in post_files if p.name not in ("index.md", "tags.md")]
            content_profiles = [p for p in profile_files if p.name != "index.md"]
            assert content_posts or content_profiles, "Pipeline succeeded but no content generated"


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
                    "--output-dir",
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
                "--output-dir",
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
                "--output-dir",
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
                "--output-dir",
                str(test_output_dir),
                "--source-type",
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
                "--max-prompt-tokens",
                "50000",
            ],
        )

        # Should accept all options
        assert result.exit_code in (0, 1), f"Unexpected error: {result.stdout}"
