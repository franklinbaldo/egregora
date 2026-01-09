import pathlib
import pytest

# Define the path to the file relative to the project root
ARTIFACT_FILE = pathlib.Path("artifacts/test_blog_1day_window.py")
SCHEDULER_TEST_FILE = pathlib.Path("tests/unit/jules/test_scheduler.py")

def test_scheduler_file_has_trailing_newline():
    """Verify that the scheduler test file ends with a newline."""
    # Ensure the file exists before reading
    if not SCHEDULER_TEST_FILE.exists():
        pytest.skip(f"Scheduler test file not found: {SCHEDULER_TEST_FILE}")

    with SCHEDULER_TEST_FILE.open("r") as f:
        content = f.read()
        assert content.endswith("\n"), "File should end with a newline"

def test_artifact_file_has_no_shebang():
    """Verify that the artifact file does not start with a shebang."""
    # Ensure the file exists before reading
    if not ARTIFACT_FILE.exists():
        pytest.skip(f"Artifact file not found: {ARTIFACT_FILE}")

    with ARTIFACT_FILE.open("r") as f:
        first_line = f.readline()
        assert not first_line.startswith("#!/"), "File should not have a shebang"
