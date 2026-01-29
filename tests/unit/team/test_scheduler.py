import sys
import unittest
from datetime import UTC, datetime, timedelta
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
    def test_ensure_jules_branch_exists_and_updates(self, mock_run: MagicMock) -> None:
        """Test ensure_jules_branch updates existing branch to match main."""
        mock_run.return_value.returncode = 0
        stateless.ensure_jules_branch()
        # fetch + rev-parse check + force-update branch
        mock_run.assert_has_calls(
            [
                call(["git", "fetch", "origin", "main"], capture_output=True),
                call(
                    ["git", "rev-parse", "--verify", f"refs/heads/{stateless.JULES_BRANCH}"],
                    capture_output=True,
                ),
                call(
                    ["git", "branch", "-f", stateless.JULES_BRANCH, "origin/main"],
                    check=True,
                    capture_output=True,
                ),
            ]
        )

    @patch("repo.scheduler.stateless.subprocess.run")
    def test_ensure_jules_branch_creates(self, mock_run: MagicMock) -> None:
        """Test ensure_jules_branch when branch missing."""

        def side_effect(cmd, **kwargs):
            if cmd[0] == "git" and cmd[1] == "rev-parse" and "--verify" in cmd:
                return MagicMock(returncode=1)
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect
        stateless.ensure_jules_branch()

        # fetch + rev-parse check + create branch
        mock_run.assert_has_calls(
            [
                call(["git", "fetch", "origin", "main"], capture_output=True),
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
        d2.name = ".hidden"  # Skipped: starts with "."

        d3 = MagicMock()
        d3.is_dir.return_value = True
        d3.name = "oracle"
        (d3 / "prompt.md.j2").exists.return_value = True  # Has prompt, discovered

        d4 = MagicMock()
        d4.is_dir.return_value = False  # Skipped: not a dir

        d5 = MagicMock()
        d5.is_dir.return_value = True
        d5.name = "franklin"  # No prompt file, skipped
        (d5 / "prompt.md.j2").exists.return_value = False
        (d5 / "prompt.md").exists.return_value = False

        mock_path.iterdir.return_value = [d1, d2, d3, d4, d5]

        personas = stateless.discover_personas()
        self.assertEqual(personas, ["oracle", "persona1"])

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


class TestSessionStaleness(unittest.TestCase):
    """Tests for session staleness detection."""

    def test_is_session_stale_no_create_time(self) -> None:
        """Session without createTime is considered stale."""
        session = {"name": "sessions/123", "state": "QUEUED"}
        self.assertTrue(stateless._is_session_stale(session))

    def test_is_session_stale_old_session(self) -> None:
        """Session older than threshold is stale."""
        # Create a timestamp 2 hours ago
        old_time = datetime.now(UTC) - timedelta(hours=2)
        session = {
            "name": "sessions/123",
            "state": "QUEUED",
            "createTime": old_time.isoformat().replace("+00:00", "Z"),
        }
        self.assertTrue(stateless._is_session_stale(session))

    def test_is_session_stale_recent_session(self) -> None:
        """Session newer than threshold is not stale."""
        # Create a timestamp 5 minutes ago
        recent_time = datetime.now(UTC) - timedelta(minutes=5)
        session = {
            "name": "sessions/123",
            "state": "QUEUED",
            "createTime": recent_time.isoformat().replace("+00:00", "Z"),
        }
        self.assertFalse(stateless._is_session_stale(session))

    def test_is_session_stale_invalid_time(self) -> None:
        """Session with invalid createTime is considered stale."""
        session = {"name": "sessions/123", "state": "QUEUED", "createTime": "not-a-date"}
        self.assertTrue(stateless._is_session_stale(session))


class TestGetActiveSession(unittest.TestCase):
    """Tests for get_active_session with staleness handling."""

    def test_returns_in_progress_session(self) -> None:
        """IN_PROGRESS session is always returned."""
        mock_client = MagicMock()
        mock_client.list_sessions.return_value = {
            "sessions": [{"name": "sessions/123", "title": "🎭 curator egregora", "state": "IN_PROGRESS"}]
        }
        result = stateless.get_active_session(mock_client, "egregora")
        self.assertIsNotNone(result)
        self.assertEqual(result["state"], "IN_PROGRESS")

    def test_skips_stale_queued_session(self) -> None:
        """Stale QUEUED session does not block new sessions."""
        mock_client = MagicMock()
        old_time = datetime.now(UTC) - timedelta(hours=2)
        mock_client.list_sessions.return_value = {
            "sessions": [
                {
                    "name": "sessions/123",
                    "title": "🎭 curator egregora",
                    "state": "QUEUED",
                    "createTime": old_time.isoformat().replace("+00:00", "Z"),
                }
            ]
        }
        result = stateless.get_active_session(mock_client, "egregora")
        self.assertIsNone(result)

    def test_returns_recent_queued_session(self) -> None:
        """Recent QUEUED session blocks new sessions."""
        mock_client = MagicMock()
        recent_time = datetime.now(UTC) - timedelta(minutes=5)
        mock_client.list_sessions.return_value = {
            "sessions": [
                {
                    "name": "sessions/123",
                    "title": "🎭 curator egregora",
                    "state": "QUEUED",
                    "createTime": recent_time.isoformat().replace("+00:00", "Z"),
                }
            ]
        }
        result = stateless.get_active_session(mock_client, "egregora")
        self.assertIsNotNone(result)
        self.assertEqual(result["state"], "QUEUED")

    def test_skips_oracle_sessions(self) -> None:
        """Oracle sessions are not returned."""
        mock_client = MagicMock()
        mock_client.list_sessions.return_value = {
            "sessions": [{"name": "sessions/123", "title": "🔮 oracle egregora", "state": "IN_PROGRESS"}]
        }
        result = stateless.get_active_session(mock_client, "egregora")
        self.assertIsNone(result)

    def test_skips_other_repo_sessions(self) -> None:
        """Sessions for other repos are not returned."""
        mock_client = MagicMock()
        mock_client.list_sessions.return_value = {
            "sessions": [{"name": "sessions/123", "title": "🎭 curator other-repo", "state": "IN_PROGRESS"}]
        }
        result = stateless.get_active_session(mock_client, "egregora")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
