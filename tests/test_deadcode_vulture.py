import subprocess
import sys
from pathlib import Path

def test_vulture_no_dead_code():
    """
    Runs vulture on the codebase to detect dead code.
    Fails if any dead code is found that is not explicitly whitelisted.
    """
    # Define paths to scan
    scan_paths = ["src", "tests"]

    # Command to run vulture
    cmd = [
        sys.executable, "-m", "vulture",
        *scan_paths,
        # "--make-whitelist", # Uncomment to generate whitelist
    ]

    # Add whitelist if it exists
    whitelist_path = Path("vulture_whitelist.py")
    if whitelist_path.exists():
        cmd.append(str(whitelist_path))

    # Run vulture
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    # Print output for debugging when test fails
    if result.returncode != 0:
        print("\nVulture found dead code:\n")
        print(result.stdout)

    assert result.returncode == 0, f"Vulture found dead code. See output above. Return code: {result.returncode}"
