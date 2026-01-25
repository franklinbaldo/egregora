"""Tests for the simplified Jules scheduler."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add .team to path so we can import repo.scheduler
REPO_ROOT = Path(__file__).parents[3]
TEAM_PATH = REPO_ROOT / ".team"
if str(TEAM_PATH) not in sys.path:
    sys.path.append(str(TEAM_PATH))

from repo.scheduler import simple
from repo.scheduler.models import PersonaConfig


class TestSimpleScheduler(unittest.TestCase):
    """Test suite for repo.scheduler.simple."""

    def test_get_next_persona_round_robin(self):
        """Test round-robin persona selection."""
        personas = ["a", "b", "c"]

        # First run (no last persona)
        self.assertEqual(simple.get_next_persona(None, personas), "a")

        # Normal rotation
        self.assertEqual(simple.get_next_persona("a", personas), "b")
        self.assertEqual(simple.get_next_persona("b", personas), "c")
        self.assertEqual(simple.get_next_persona("c", personas), "a")

        # Unknown last persona (start over)
        self.assertEqual(simple.get_next_persona("z", personas), "a")

        # Empty list
        self.assertIsNone(simple.get_next_persona("a", []))

    @patch("repo.scheduler.simple.TeamClient")
    def test_get_last_persona_from_api(self, mock_client_cls):
        """Test retrieving the last persona from API sessions."""
        mock_client = mock_client_cls.return_value

        # Mock sessions response
        mock_client.list_sessions.return_value = {
            "sessions": [
                {"title": "🤖 curator my-repo", "createTime": "2023-01-02T10:00:00Z"},
                {"title": "📝 writer my-repo", "createTime": "2023-01-01T10:00:00Z"},
                {"title": "Ignore other repo", "createTime": "2023-01-03T10:00:00Z"},
            ]
        }

        # Mock discover_personas to validate persona names
        with patch("repo.scheduler.simple.discover_personas", return_value=["curator", "writer"]):
            last = simple.get_last_persona_from_api(mock_client, "my-repo")

            # Should match "curator" (most recent matching repo)
            self.assertEqual(last, "curator")

    @patch("subprocess.run")
    def test_merge_completed_prs(self, mock_run):
        """Test merging completed PRs."""
        # Mock gh pr list output
        pr_list_json = """
        [
            {
                "number": 1,
                "isDraft": true,
                "statusCheckRollup": [{"conclusion": "SUCCESS"}],
                "mergeable": "MERGEABLE"
            },
            {
                "number": 2,
                "isDraft": false,
                "statusCheckRollup": [{"conclusion": "FAILURE"}],
                "mergeable": "MERGEABLE"
            }
        ]
        """
        mock_run.return_value.stdout = pr_list_json

        merged_count = simple.merge_completed_prs()

        self.assertEqual(merged_count, 1)

        # Verify gh pr ready called for #1
        mock_run.assert_any_call(
            ["gh", "pr", "ready", "1"],
            check=True,
            capture_output=True,
        )

        # Verify gh pr merge called for #1
        mock_run.assert_any_call(
            ["gh", "pr", "merge", "1", "--squash", "--delete-branch"],
            check=True,
            capture_output=True,
        )

    @patch("subprocess.run")
    def test_discover_personas(self, mock_run):
        """Test discovering personas from filesystem."""
        # Mock _get_persona_dir to return a temp path
        with patch("repo.scheduler.simple._get_persona_dir") as mock_dir_func:
            # Create a fake directory structure using Path mock
            mock_path = MagicMock()
            mock_dir_func.return_value = mock_path
            mock_path.exists.return_value = True

            # Mock entries
            entry1 = MagicMock()
            entry1.is_dir.return_value = True
            entry1.name = "persona1"
            # (path / "prompt.md.j2").exists()
            (entry1 / "prompt.md.j2").exists.return_value = True

            entry2 = MagicMock()
            entry2.is_dir.return_value = True
            entry2.name = "persona2"
            (entry2 / "prompt.md.j2").exists.return_value = False
            (entry2 / "prompt.md").exists.return_value = True

            entry3 = MagicMock() # Excluded
            entry3.is_dir.return_value = True
            entry3.name = "franklin"

            mock_path.iterdir.return_value = [entry1, entry2, entry3]

            personas = simple.discover_personas()

            self.assertEqual(personas, ["persona1", "persona2"])

    @patch("repo.scheduler.simple.ensure_jules_branch")
    @patch("repo.scheduler.simple.TeamClient")
    def test_create_session(self, mock_client_cls, mock_ensure_branch):
        """Test creating a Jules session."""
        mock_client = mock_client_cls.return_value
        mock_client.create_session.return_value = {"name": "projects/123/locations/us/sessions/abc-123"}

        persona = PersonaConfig(
            id="test-persona",
            emoji="🤖",
            description="Test",
            prompt_body="Hello",
            path="path/to/p",
            journal_entries=""
        )

        repo_info = {"owner": "test-owner", "repo": "test-repo"}

        result = simple.create_session(mock_client, persona, repo_info)

        self.assertTrue(result.success)
        self.assertEqual(result.session_id, "abc-123")

        # Verify calls
        mock_ensure_branch.assert_called_once()
        mock_client.create_session.assert_called_once()

    @patch("repo.scheduler.simple.merge_completed_prs")
    @patch("repo.scheduler.simple.discover_personas")
    @patch("repo.scheduler.simple.get_last_persona_from_api")
    @patch("repo.scheduler.simple.PersonaLoader")
    @patch("repo.scheduler.simple.create_session")
    @patch("repo.scheduler.simple.TeamClient")
    @patch("repo.scheduler.simple.get_repo_info")
    @patch("repo.scheduler.simple.get_open_prs")
    def test_run_scheduler_flow(
        self,
        mock_get_open_prs,
        mock_get_repo,
        mock_client_cls,
        mock_create_session,
        mock_loader_cls,
        mock_get_last,
        mock_discover,
        mock_merge
    ):
        """Test the full scheduler flow."""
        # Setup mocks
        mock_get_repo.return_value = {"owner": "o", "repo": "r"}
        mock_merge.return_value = 1
        mock_discover.return_value = ["p1", "p2"]
        mock_get_last.return_value = "p1"

        # Mock loader
        mock_loader = mock_loader_cls.return_value
        p1 = PersonaConfig(id="p1", emoji="1", description="d", prompt_body="b", path="p", journal_entries="")
        p2 = PersonaConfig(id="p2", emoji="2", description="d", prompt_body="b", path="p", journal_entries="")
        mock_loader.load_personas.return_value = [p1, p2]

        # Mock create session result
        mock_create_session.return_value = simple.SchedulerResult(success=True, message="Created", session_id="sess-1")

        # Run
        result = simple.run_scheduler(dry_run=False)

        self.assertTrue(result.success)
        self.assertEqual(result.merged_count, 1)
        self.assertEqual(result.session_id, "sess-1")

        # Verify next persona logic (p1 -> p2)
        # create_session should be called with p2
        args, _ = mock_create_session.call_args
        self.assertEqual(args[1].id, "p2")


if __name__ == "__main__":
    unittest.main()
