"""Integration tests for the 'egregora demo' CLI command."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()


@pytest.fixture
def test_output_dir(tmp_path: Path) -> Path:
    """Temporary output directory for tests."""
    return tmp_path


def test_demo_command_with_output_dir(test_output_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the 'egregora demo' command with an explicit output directory."""
    monkeypatch.chdir(test_output_dir)

    result = runner.invoke(app, ["demo", "--output-dir", "test-demo"])

    # The command should complete successfully or fail gracefully if no API key is set.
    # Exit code 0 for success, 1 for a pipeline error (acceptable in this test).
    assert result.exit_code in (0, 1), f"Command failed unexpectedly: {result.stdout}"

    # Check that the output directory was created.
    demo_dir = test_output_dir / "test-demo"
    assert demo_dir.is_dir(), "The demo directory was not created."

    # Check for the presence of key files and directories.
    assert (demo_dir / "mkdocs.yml").exists(), "mkdocs.yml was not created."
    assert (demo_dir / "docs").is_dir(), "'docs' directory was not created."
    assert (demo_dir / "docs" / "posts").is_dir(), "'posts' directory was not created."


def test_demo_command_with_default_output_dir(test_output_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the 'egregora demo' command with the default output directory."""
    monkeypatch.chdir(test_output_dir)

    result = runner.invoke(app, ["demo"])

    # The command should complete successfully or fail gracefully if no API key is set.
    # Exit code 0 for success, 1 for a pipeline error (acceptable in this test).
    assert result.exit_code in (0, 1), f"Command failed unexpectedly: {result.stdout}"

    # Check that the default output directory was created.
    demo_dir = test_output_dir / "demo"
    assert demo_dir.is_dir(), "The default demo directory was not created."

    # Check for the presence of key files and directories.
    assert (demo_dir / "mkdocs.yml").exists(), "mkdocs.yml was not created."
    assert (demo_dir / "docs").is_dir(), "'docs' directory was not created."
    assert (demo_dir / "docs" / "posts").is_dir(), "'posts' directory was not created."
