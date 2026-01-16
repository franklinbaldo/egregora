import subprocess

import pytest


@pytest.mark.deadcode
def test_vulture_finds_no_dead_code():
    """
    Runs vulture to ensure no dead code is found.
    """
    try:
        result = subprocess.run(
            ["uv", "run", "vulture", "src", "tests", "--min-confidence=80"],
            check=False,  # Don't raise exception on non-zero exit
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.fail(
                f"Vulture found dead code (exit code {result.returncode}):\n"
                f"--- STDOUT ---\n{result.stdout}\n"
                f"--- STDERR ---\n{result.stderr}",
                pytrace=False,
            )
    except FileNotFoundError:
        pytest.fail("vulture command not found. Is it installed in the uv environment?", pytrace=False)
