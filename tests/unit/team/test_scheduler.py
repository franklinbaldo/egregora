import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# Add .team to path so we can import repo.scheduler
# We use relative path from repo root
REPO_ROOT = Path(__file__).parents[3]
TEAM_PATH = REPO_ROOT / ".team"
if str(TEAM_PATH) not in sys.path:
    sys.path.append(str(TEAM_PATH))

from repo.scheduler import stateless  # noqa: E402
from repo.scheduler.models import PersonaConfig  # noqa: E402


class TestStatelessScheduler(unittest.TestCase):
    @patch("repo.scheduler.stateless.subprocess.run")
    def test_ensure_jules_branch_exists(self, mock_run: MagicMock) -> None:
        """Test ensure_jules_branch when branch exists."""
        mock_run.return_value.returncode = 0
        stateless.ensure_jules_branch()
        # Verify it checks existence
        mock_run.assert_called_with(
            ["git", "rev-parse", "--verify", f"refs/heads/{stateless.JULES_BRANCH}"],
            capture_output=True,
        )
        # Verify it doesn't create
        self.assertEqual(mock_run.call_count, 1)

    @patch("repo.scheduler.stateless.subprocess.run")
    def test_ensure_jules_branch_creates(self, mock_run: MagicMock) -> None:
        """Test ensure_jules_branch when branch missing."""

        # First call fails (check), second succeeds (create)
        def side_effect(cmd, **kwargs):
            if cmd[0] == "git" and cmd[1] == "rev-parse":
                return MagicMock(returncode=1)
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect
        stateless.ensure_jules_branch()

        self.assertEqual(mock_run.call_count, 2)
        mock_run.assert_has_calls(
            [
                call(
                    ["git", "rev-parse", "--verify", f"refs/heads/{stateless.JULES_BRANCH}"],
                    capture_output=True,
                ),
                call(
                    ["git", "branch", stateless.JULES_BRANCH, "origin/main"], check=True, capture_output=True
                ),
            ]
        )

    @patch("repo.scheduler.stateless._get_persona_dir")
    def test_discover_personas(self, mock_get_dir: MagicMock) -> None:
        """Test discover_personas filtering."""
        mock_path = MagicMock()
        mock_get_dir.return_value = mock_path
        mock_path.exists.return_value = True

        # Setup directories
        d1 = MagicMock()
        d1.is_dir.return_value = True
        d1.name = "persona1"
        (d1 / "prompt.md.j2").exists.return_value = True

        d2 = MagicMock()
        d2.is_dir.return_value = True
        d2.name = ".hidden"

        d3 = MagicMock()
        d3.is_dir.return_value = True
        d3.name = "oracle"  # Excluded

        d4 = MagicMock()
        d4.is_dir.return_value = False  # Not dir

        mock_path.iterdir.return_value = [d1, d2, d3, d4]

        personas = stateless.discover_personas()
        self.assertEqual(personas, ["persona1"])

    def test_get_next_persona(self) -> None:
        personas = ["a", "b", "c"]
        self.assertEqual(stateless.get_next_persona("a", personas), "b")
        self.assertEqual(stateless.get_next_persona("c", personas), "a")
        self.assertEqual(stateless.get_next_persona(None, personas), "a")
        self.assertEqual(stateless.get_next_persona("z", personas), "a")
        self.assertIsNone(stateless.get_next_persona("a", []))

    @patch("repo.scheduler.stateless.ensure_jules_branch")
    def test_create_session(self, mock_ensure: MagicMock) -> None:
        """Test create_session."""
        mock_client = MagicMock()
        mock_client.create_session.return_value = {"name": "sessions/123"}

        persona = MagicMock(spec=PersonaConfig)
        persona.id = "test-p"
        persona.emoji = "T"
        persona.prompt_body = "prompt"

        repo_info = {"owner": "o", "repo": "r"}

        result = stateless.create_session(mock_client, persona, repo_info)

        self.assertTrue(result.success)
        self.assertEqual(result.session_id, "123")
        mock_ensure.assert_called_once()
        mock_client.create_session.assert_called_once()


if __name__ == "__main__":
    unittest.main()
