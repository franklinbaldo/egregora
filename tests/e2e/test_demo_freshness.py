"""
E2E test to ensure the demo/ directory is up-to-date.
"""
import filecmp
import subprocess
import sys
from pathlib import Path

import pytest

# The root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent
DEMO_DIR = ROOT_DIR / "demo"


def run_command(command: list[str], cwd: Path):
    """Helper function to run a command and handle errors."""
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Command `{' '.join(command)}` failed with exit code {result.returncode}.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def compare_dirs(dir1: Path, dir2: Path):
    """
    Compares two directories recursively. Returns True if they are the same,
    False otherwise.
    """
    dirs_cmp = filecmp.dircmp(dir1, dir2)
    # Check for different files in common directories
    if dirs_cmp.diff_files:
        return False, f"Different files found: {dirs_cmp.diff_files}"
    # Check for files only in the first directory
    if dirs_cmp.left_only:
        return False, f"Files only in {dir1}: {dirs_cmp.left_only}"
    # Check for files only in the second directory
    if dirs_cmp.right_only:
        return False, f"Files only in {dir2}: {dirs_cmp.right_only}"
    # Recurse into subdirectories
    for common_dir in dirs_cmp.common_dirs:
        new_dir1 = dir1 / common_dir
        new_dir2 = dir2 / common_dir
        are_same, reason = compare_dirs(new_dir1, new_dir2)
        if not are_same:
            return False, reason
    return True, ""


@pytest.mark.slow
def test_demo_directory_is_up_to_date(tmp_path: Path):
    """
    Generates a fresh demo site and compares it with the existing `demo/` directory.
    If they are not identical, the test fails.
    """
    if not DEMO_DIR.exists():
        pytest.skip(
            "The `demo/` directory does not exist. "
            "Run `uv run egregora demo` to create it."
        )

    generated_demo_path = tmp_path / "generated_demo"
    generated_demo_path.mkdir()

    # Generate a fresh demo site
    run_command(
        [
            sys.executable,
            "-m",
            "egregora.cli.main",
            "demo",
            "--output-dir",
            str(generated_demo_path),
        ],
        cwd=ROOT_DIR,
    )

    # Compare the generated site with the existing demo directory
    are_same, reason = compare_dirs(DEMO_DIR, generated_demo_path)

    if not are_same:
        pytest.fail(
            f"The `demo/` directory is not up-to-date. "
            f"Reason: {reason}.\n"
            "Please run `uv run egregora demo` and commit the changes."
        )
