"""Git-related utility functions."""
import subprocess

def get_git_commit_sha() -> str | None:
    """Get current git commit SHA for reproducibility tracking.

    Returns:
        Git commit SHA (e.g., "a1b2c3d4..."), or None if not in git repo

    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
