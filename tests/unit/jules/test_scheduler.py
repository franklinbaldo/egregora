import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add .jules to path so we can import jules.scheduler
# We use relative path from repo root
REPO_ROOT = Path(__file__).parents[3]
JULES_PATH = REPO_ROOT / ".jules"
if str(JULES_PATH) not in sys.path:
    sys.path.append(str(JULES_PATH))

from jules.scheduler import (  # type: ignore[import-not-found] # noqa: E402
    JULES_BRANCH,
    ensure_jules_branch_exists,
    update_jules_from_main,
)


class TestJulesSchedulerUpdate(unittest.TestCase):
    @patch("subprocess.run")
    def test_update_jules_from_main_success(self, mock_run: MagicMock) -> None:
        """Test that update_jules_from_main runs the correct git commands on success."""
        # Mock successful execution
        mock_run.return_value.returncode = 0

        result = update_jules_from_main()

        self.assertTrue(result)

        # Verify calls
        # Config user
        mock_run.assert_any_call(["git", "config", "user.name", "Jules Bot"], check=False)
        mock_run.assert_any_call(["git", "config", "user.email", "jules-bot@google.com"], check=False)

        # Checkout
        mock_run.assert_any_call(
            ["git", "checkout", "-B", JULES_BRANCH, f"origin/{JULES_BRANCH}"], check=True, capture_output=True
        )

        # Merge
        mock_run.assert_any_call(
            ["git", "merge", "origin/main", "--no-edit"], check=True, capture_output=True
        )

        # Push
        mock_run.assert_any_call(["git", "push", "origin", JULES_BRANCH], check=True, capture_output=True)

    @patch("jules.scheduler_legacy.rotate_drifted_jules_branch")
    @patch("subprocess.run")
    def test_update_jules_from_main_failure(self, mock_run: MagicMock, mock_rotate: MagicMock) -> None:
        """Test that update_jules_from_main fails gracefully and rotates on error."""

        # Mock failure during merge
        def side_effect(*args: object, **kwargs: object) -> MagicMock:
            cmd = args[0]
            if isinstance(cmd, list) and "merge" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"Conflict")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        result = update_jules_from_main()

        self.assertFalse(result)
        mock_rotate.assert_called_once()

    @patch("jules.scheduler_legacy.update_jules_from_main")
    @patch("jules.scheduler_legacy.is_jules_drifted")
    @patch("subprocess.run")
    def test_ensure_jules_branch_exists_calls_update(
        self, mock_run: MagicMock, mock_is_drifted: MagicMock, mock_update: MagicMock
    ) -> None:
        """Test that ensure_jules_branch_exists calls update when branch is healthy."""
        # Mock fetch success
        mock_run.return_value.returncode = 0
        # Mock branch exists
        mock_run.return_value.stdout = "refs/heads/jules"

        # Mock not drifted
        mock_is_drifted.return_value = False

        # Mock update success
        mock_update.return_value = True

        ensure_jules_branch_exists()

        mock_update.assert_called_once()

    @patch("jules.scheduler_legacy.update_jules_from_main")
    @patch("jules.scheduler_legacy.is_jules_drifted")
    @patch("subprocess.run")
    def test_ensure_jules_branch_exists_fallback_on_update_fail(
        self, mock_run: MagicMock, mock_is_drifted: MagicMock, mock_update: MagicMock
    ) -> None:
        """Test that ensure_jules_branch_exists recreates branch if update fails."""
        # Mock fetch success
        # We need to simulate the sequence of subprocess calls
        # 1. git fetch
        # 2. git ls-remote (returns branch exists)
        # 3. git rev-parse origin/main (for recreation)
        # 4. git push --force (recreation)

        def run_side_effect(*args: object, **kwargs: object) -> MagicMock:
            cmd = args[0]
            if cmd == ["git", "fetch", "origin"]:
                return MagicMock(returncode=0)
            if cmd == ["git", "ls-remote", "--heads", "origin", JULES_BRANCH]:
                return MagicMock(stdout="hash refs/heads/jules\n")
            if cmd == ["git", "rev-parse", "origin/main"]:
                return MagicMock(stdout="main_sha\n")
            if isinstance(cmd, list) and cmd[:4] == ["git", "push", "--force", "origin"]:
                return MagicMock(returncode=0)
            return MagicMock()

        mock_run.side_effect = run_side_effect

        # Mock not drifted
        mock_is_drifted.return_value = False

        # Mock update FAILURE
        mock_update.return_value = False

        ensure_jules_branch_exists()

        mock_update.assert_called_once()
        # Verify it proceeded to recreate (calls git rev-parse origin/main)
        mock_run.assert_any_call(
            ["git", "rev-parse", "origin/main"], capture_output=True, text=True, check=True
        )


if __name__ == "__main__":
    unittest.main()