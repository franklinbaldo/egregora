"""Test to enforce absolute imports only (no relative imports)."""

import subprocess
import tempfile
from pathlib import Path


def test_relative_imports_are_forbidden() -> None:
    """Test that ruff detects and rejects relative imports (TID252)."""
    # Create a temporary Python file with a relative import
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=Path.cwd()
    ) as tmp:
        tmp.write("from ..config import ModelConfig\n")
        tmp.write("from .models import Something\n")
        tmp_path = Path(tmp.name)

    try:
        # Run ruff check on the file
        result = subprocess.run(
            ["uvx", "ruff", "check", str(tmp_path)],
            check=False, capture_output=True,
            text=True,
        )

        # Should fail (non-zero exit code) because of relative imports
        assert result.returncode != 0, "Ruff should have detected relative imports"

        # Check that the specific rule TID252 is mentioned
        assert (
            "TID252" in result.stdout
        ), f"Expected TID252 error in output, got: {result.stdout}"

        # Verify the error message mentions relative imports
        assert any(
            keyword in result.stdout.lower()
            for keyword in ["relative", "import", "absolute"]
        ), f"Expected relative import error message, got: {result.stdout}"

    finally:
        # Clean up
        tmp_path.unlink(missing_ok=True)


def test_absolute_imports_are_allowed() -> None:
    """Test that ruff allows absolute imports."""
    # Create a temporary Python file with an absolute import
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=Path.cwd()
    ) as tmp:
        tmp.write("from egregora.config import ModelConfig\n")
        tmp.write("from egregora.core.models import Something\n")
        tmp_path = Path(tmp.name)

    try:
        # Run ruff check on the file
        result = subprocess.run(
            ["uvx", "ruff", "check", str(tmp_path)],
            check=False, capture_output=True,
            text=True,
        )

        # Should pass (TID252 should not trigger for absolute imports)
        # Note: Other rules might fail, but TID252 should not be present
        assert (
            "TID252" not in result.stdout
        ), f"TID252 should not trigger for absolute imports, got: {result.stdout}"

    finally:
        # Clean up
        tmp_path.unlink(missing_ok=True)
