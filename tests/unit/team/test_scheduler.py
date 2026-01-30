import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

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

        def side_effect(cmd, **kwargs):
            result = MagicMock(returncode=0)
            # ls-remote returns non-empty stdout when branch exists
            if cmd[1:3] == ["ls-remote", "--heads"]:
                result.stdout = f"abc123\trefs/heads/{stateless.JULES_BRANCH}\n"
            return result

        mock_run.side_effect = side_effect
        stateless.ensure_jules_branch()
        # Verify essential calls are made
        mock_run.assert_any_call(["git", "fetch", "origin", "main"], capture_output=True)
        mock_run.assert_any_call(
            ["git", "ls-remote", "--heads", "origin", stateless.JULES_BRANCH],
            capture_output=True,
            text=True,
        )
        mock_run.assert_any_call(
            ["git", "branch", "-f", stateless.JULES_BRANCH, "origin/main"],
            check=True,
            capture_output=True,
        )

    @patch("repo.scheduler.stateless.subprocess.run")
    def test_ensure_jules_branch_creates(self, mock_run: MagicMock) -> None:
        """Test ensure_jules_branch when branch missing on remote."""

        def side_effect(cmd, **kwargs):
            result = MagicMock(returncode=0)
            # ls-remote returns empty stdout when branch doesn't exist
            if cmd[1:3] == ["ls-remote", "--heads"]:
                result.stdout = ""
            return result

        mock_run.side_effect = side_effect
        stateless.ensure_jules_branch()

        # Verify essential calls are made
        mock_run.assert_any_call(["git", "fetch", "origin", "main"], capture_output=True)
        mock_run.assert_any_call(
            ["git", "ls-remote", "--heads", "origin", stateless.JULES_BRANCH],
            capture_output=True,
            text=True,
        )
        mock_run.assert_any_call(
            ["git", "branch", stateless.JULES_BRANCH, "origin/main"], check=True, capture_output=True
        )
        mock_run.assert_any_call(
            ["git", "push", "-u", "origin", stateless.JULES_BRANCH], check=True, capture_output=True
        )

    @patch("repo.scheduler.stateless._get_persona_dir")
    def test_discover_personas(self, mock_get_dir: MagicMock) -> None:
        """Test discover_personas filtering with frontmatter opt-out."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mock_get_dir.return_value = base

            # persona1: normal, should be discovered
            (base / "persona1").mkdir()
            (base / "persona1" / "prompt.md.j2").write_text("---\nid: persona1\nemoji: '1'\n---\nHello")

            # .hidden: starts with ".", should be skipped
            (base / ".hidden").mkdir()
            (base / ".hidden" / "prompt.md.j2").write_text("---\nid: hidden\n---\n")

            # oracle: scheduled: false, should be skipped
            (base / "oracle").mkdir()
            (base / "oracle" / "prompt.md.j2").write_text(
                "---\nid: oracle\nemoji: '🔮'\nscheduled: false\nautomation_mode: MANUAL\n---\nOracle"
            )

            # noprompt: no prompt file, should be skipped
            (base / "noprompt").mkdir()

            # curator: normal, should be discovered
            (base / "curator").mkdir()
            (base / "curator" / "prompt.md.j2").write_text("---\nid: curator\nemoji: '🎭'\n---\nCurator")

            personas = stateless.discover_personas()
            self.assertEqual(personas, ["curator", "persona1"])

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


class TestMergeCompletedPrs(unittest.TestCase):
    @patch("repo.scheduler.stateless.subprocess.run")
    def test_merge_jules_pr_by_url(self, mock_run: MagicMock) -> None:
        """Test merges Jules PR identified by URL."""
        import json

        pr_data = [
            {
                "number": 123,
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "body": "See https://jules.google.com/sessions/abc",
                "author": {"login": "human"},
            }
        ]
        mock_run.return_value.stdout = json.dumps(pr_data)

        merged = stateless.merge_completed_prs()
        self.assertEqual(merged, 1)

        # Should verify merge call
        # We need to find the call with 'merge' in args
        merge_calls = [
            call
            for call in mock_run.call_args_list
            if call[0][0] == ["gh", "pr", "merge", "123", "--merge", "--delete-branch", "--admin"]
        ]
        self.assertTrue(merge_calls)

    @patch("repo.scheduler.stateless.subprocess.run")
    def test_merge_jules_pr_by_author(self, mock_run: MagicMock) -> None:
        """Test merges Jules PR identified by bot author."""
        import json

        pr_data = [
            {
                "number": 124,
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "body": "Fix stuff",
                "author": {"login": "google-labs-jules"},
            }
        ]
        mock_run.return_value.stdout = json.dumps(pr_data)

        merged = stateless.merge_completed_prs()
        self.assertEqual(merged, 1)

    @patch("repo.scheduler.stateless.subprocess.run")
    def test_skip_non_jules_pr(self, mock_run: MagicMock) -> None:
        """Test skips PR not from Jules."""
        import json

        pr_data = [
            {
                "number": 125,
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "body": "Regular PR",
                "author": {"login": "human"},
            }
        ]
        mock_run.return_value.stdout = json.dumps(pr_data)

        merged = stateless.merge_completed_prs()
        self.assertEqual(merged, 0)
        # Should NOT call merge
        for call in mock_run.call_args_list:
            args = call[0][0]
            if "merge" in args and "pr" in args:
                self.fail("Should not merge non-Jules PR")

    @patch("repo.scheduler.stateless.subprocess.run")
    def test_skip_conflicting_pr(self, mock_run: MagicMock) -> None:
        """Test skips PR with conflicts."""
        import json

        pr_data = [
            {
                "number": 126,
                "isDraft": False,
                "mergeable": "CONFLICTING",
                "body": "https://jules.google.com/sessions/abc",
                "author": {"login": "human"},
            }
        ]
        mock_run.return_value.stdout = json.dumps(pr_data)

        merged = stateless.merge_completed_prs()
        self.assertEqual(merged, 0)

    @patch("repo.scheduler.stateless.subprocess.run")
    def test_mark_draft_ready_before_merge(self, mock_run: MagicMock) -> None:
        """Test marks draft PR as ready before merging."""
        import json

        pr_data = [
            {
                "number": 127,
                "isDraft": True,
                "mergeable": "MERGEABLE",
                "body": "https://jules.google.com/sessions/abc",
                "author": {"login": "human"},
            }
        ]
        mock_run.return_value.stdout = json.dumps(pr_data)

        merged = stateless.merge_completed_prs()
        self.assertEqual(merged, 1)

        # Verify ready call
        ready_calls = [call for call in mock_run.call_args_list if call[0][0] == ["gh", "pr", "ready", "127"]]
        self.assertTrue(ready_calls)

    @patch("repo.scheduler.stateless.subprocess.run")
    def test_gh_list_failure(self, mock_run: MagicMock) -> None:
        """Test handles gh list failure gracefully."""
        mock_run.side_effect = Exception("gh failed")
        merged = stateless.merge_completed_prs()
        self.assertEqual(merged, 0)


class TestOracleSession(unittest.TestCase):
    @patch("repo.scheduler.stateless._get_persona_dir")
    def test_get_or_create_oracle_session_reuses_existing(self, mock_get_dir: MagicMock) -> None:
        """Test reuses existing Oracle session."""
        mock_client = MagicMock()
        mock_client.list_sessions.return_value = {
            "sessions": [
                {
                    "name": "sessions/oracle-123",
                    "title": "🔮 oracle repo",
                    "state": "IN_PROGRESS",
                }
            ]
        }
        repo_info = {"owner": "owner", "repo": "repo"}

        sid = stateless.get_or_create_oracle_session(mock_client, repo_info)
        self.assertEqual(sid, "oracle-123")
        mock_client.create_session.assert_not_called()

    @patch("repo.scheduler.stateless._get_persona_dir")
    def test_get_or_create_oracle_session_creates_new(self, mock_get_dir: MagicMock) -> None:
        """Test creates new Oracle session if none exists."""
        mock_client = MagicMock()
        mock_client.list_sessions.return_value = {"sessions": []}
        mock_client.create_session.return_value = {"name": "sessions/oracle-new"}

        repo_info = {"owner": "owner", "repo": "repo"}

        # Mock prompt file loading
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mock_get_dir.return_value = base
            (base / "oracle").mkdir()
            (base / "oracle" / "prompt.md.j2").write_text(
                "---\nid: oracle\nautomation_mode: FULL\n---\nPrompt"
            )

            sid = stateless.get_or_create_oracle_session(mock_client, repo_info)
            self.assertEqual(sid, "oracle-new")
            mock_client.create_session.assert_called_once()
            # Verify prompt content was used
            call_args = mock_client.create_session.call_args[1]
            self.assertEqual(call_args["prompt"], "Prompt")
            self.assertEqual(call_args["automation_mode"], "FULL")

    @patch("repo.scheduler.stateless._get_persona_dir")
    def test_get_or_create_oracle_session_fallback_prompt(self, mock_get_dir: MagicMock) -> None:
        """Test uses fallback prompt if file missing."""
        mock_client = MagicMock()
        mock_client.list_sessions.return_value = {"sessions": []}
        mock_client.create_session.return_value = {"name": "sessions/oracle-new"}

        repo_info = {"owner": "owner", "repo": "repo"}
        mock_get_dir.return_value = Path("/non/existent/path")

        sid = stateless.get_or_create_oracle_session(mock_client, repo_info)
        self.assertEqual(sid, "oracle-new")

        call_args = mock_client.create_session.call_args[1]
        self.assertIn("You are the Oracle", call_args["prompt"])


class TestUnblockStuckSessions(unittest.TestCase):
    def test_extract_question_from_activities(self) -> None:
        """Test extracts question from session activities."""
        mock_client = MagicMock()
        mock_client.get_activities.return_value = {
            "activities": [
                {
                    "originator": "AGENT",
                    "createTime": "2024-01-01T10:00:00Z",
                    "text": "I need help with X?",
                },
                {
                    "originator": "USER",
                    "createTime": "2024-01-01T09:00:00Z",
                    "text": "Do X",
                },
            ]
        }
        q = stateless.extract_question_from_session(mock_client, "s1")
        self.assertEqual(q, "I need help with X?")

    def test_extract_question_fallback(self) -> None:
        """Test falls back to last message if no question mark."""
        mock_client = MagicMock()
        mock_client.get_activities.return_value = {
            "activities": [
                {
                    "originator": "AGENT",
                    "createTime": "2024-01-01T10:00:00Z",
                    "text": "Just stating facts",
                }
            ]
        }
        q = stateless.extract_question_from_session(mock_client, "s1")
        self.assertEqual(q, "Just stating facts")

    def test_extract_question_none(self) -> None:
        """Test returns None if no activities."""
        mock_client = MagicMock()
        mock_client.get_activities.return_value = {"activities": []}
        q = stateless.extract_question_from_session(mock_client, "s1")
        self.assertIsNone(q)

    @patch("repo.scheduler.stateless.get_or_create_oracle_session")
    def test_unblock_stuck_sessions_flow(self, mock_get_oracle: MagicMock) -> None:
        """Test full unblock flow."""
        mock_client = MagicMock()
        mock_client.list_sessions.return_value = {
            "sessions": [
                {
                    "name": "sessions/stuck1",
                    "title": "stuck session repo",
                    "state": "AWAITING_USER_FEEDBACK",
                }
            ]
        }
        # Activities has a question
        mock_client.get_activities.return_value = {
            "activities": [{"originator": "AGENT", "text": "Help me?", "createTime": "2024-01-01T10:00:00Z"}]
        }

        mock_get_oracle.return_value = "oracle-sid"
        repo_info = {"owner": "o", "repo": "repo"}

        count = stateless.unblock_stuck_sessions(mock_client, repo_info)
        self.assertEqual(count, 1)

        # Verify sent to oracle
        mock_client.send_message.assert_any_call("oracle-sid", unittest.mock.ANY)
        # Verify unblock message sent to stuck session
        mock_client.send_message.assert_any_call("stuck1", unittest.mock.ANY)

    def test_auto_approve_plan(self) -> None:
        """Test auto-approves plan for AWAITING_PLAN_APPROVAL."""
        mock_client = MagicMock()
        stuck = stateless.StuckSession(
            session_id="s1",
            title="t",
            state="AWAITING_PLAN_APPROVAL",
        )
        repo_info = {"owner": "o", "repo": "r"}

        # Mock extract_question to return None so it falls back to approval
        # (Assuming no question = approve plan logic in facilitate_stuck_session)
        # But wait, facilitate_stuck_session calls extract_question_from_session.
        # If it returns None, it tries to approve.

        with patch("repo.scheduler.stateless.extract_question_from_session", return_value=None):
            result = stateless.facilitate_stuck_session(mock_client, stuck, "oracle", repo_info)
            self.assertTrue(result)
            mock_client.approve_plan.assert_called_once_with("s1")


if __name__ == "__main__":
    unittest.main()
