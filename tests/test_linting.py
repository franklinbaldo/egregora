import subprocess
import sys

import pytest


def test_ruff_format():
    """Checks that ruff format check passes."""
    try:
        subprocess.run(
            [sys.executable, "-m", "ruff", "format", "--check", "."],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(
            f"Ruff format check failed. Run 'ruff format .' to fix.\\n{e.stdout}\\n{e.stderr}",
            pytrace=False,
        )
    except FileNotFoundError:
        pytest.fail("ruff command not found. Make sure it is installed and in your PATH.")


def test_ruff_lint():
    """Checks that ruff lint check passes."""
    try:
        subprocess.run(
            [sys.executable, "-m", "ruff", "check", "."],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(
            f"Ruff lint check failed. Run 'ruff check --fix .' to fix.\\n{e.stdout}\\n{e.stderr}",
            pytrace=False,
        )
    except FileNotFoundError:
        pytest.fail("ruff command not found. Make sure it is installed and in your PATH.")
