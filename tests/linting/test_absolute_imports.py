"""Test that ruff enforces absolute imports (TID252 rule)."""

import subprocess
import tempfile
from pathlib import Path


def test_ruff_rejects_relative_imports():
    """Verify ruff detects and rejects relative imports (TID252 rule)."""
    # Create a temporary Python file with a relative import
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("from ..config import ModelConfig\n")
        temp_file = Path(f.name)

    try:
        # Run ruff check on the file
        result = subprocess.run(
            ["ruff", "check", str(temp_file)],
            capture_output=True,
            text=True,
        )

        # Ruff should detect the TID252 violation
        assert result.returncode != 0, "Ruff should reject relative imports"
        assert "TID252" in result.stdout, "Should flag TID252 (relative import violation)"

    finally:
        temp_file.unlink()


def test_ruff_allows_absolute_imports():
    """Verify ruff allows absolute imports."""
    # Create a temporary Python file with an absolute import
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("from egregora.config import ModelConfig\n")
        temp_file = Path(f.name)

    try:
        # Run ruff check on the file
        result = subprocess.run(
            ["ruff", "check", str(temp_file)],
            capture_output=True,
            text=True,
        )

        # Ruff should not flag any issues with absolute imports
        # (it may still return non-zero for other rules, but not TID252)
        assert "TID252" not in result.stdout, "Should not flag absolute imports"

    finally:
        temp_file.unlink()


def test_no_relative_imports_in_codebase():
    """Verify the entire codebase uses absolute imports."""
    # Run ruff check on the entire source directory
    result = subprocess.run(
        ["ruff", "check", "src/egregora", "--select", "TID252"],
        capture_output=True,
        text=True,
    )

    # Should find no TID252 violations
    assert result.returncode == 0, f"Found relative imports in codebase:\n{result.stdout}"
    assert "TID252" not in result.stdout, "Codebase should have no relative imports"
