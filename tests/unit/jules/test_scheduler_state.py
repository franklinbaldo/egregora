import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

# Add .jules to path
REPO_ROOT = Path(__file__).parents[3]
JULES_PATH = REPO_ROOT / ".jules"
if str(JULES_PATH) not in sys.path:
    sys.path.append(str(JULES_PATH))

from jules.scheduler_state import PersistentCycleState, commit_cycle_state  # noqa: E402


class TestPersistentCycleState(unittest.TestCase):
    def setUp(self):
        self.test_dir = TemporaryDirectory()
        self.test_path = Path(self.test_dir.name) / "cycle_state.json"

    def tearDown(self):
        self.test_dir.cleanup()

    def test_save_includes_history_and_tracks(self):
        """Test that save() includes 'history' and 'tracks' keys."""
        state = PersistentCycleState()
        state.record_session("persona1", 0, "session1", 123)
        state.save(self.test_path)

        with self.test_path.open() as f:
            data = json.load(f)

        self.assertIn("history", data)
        self.assertIn("tracks", data)
        self.assertEqual(len(data["history"]), 1)
        self.assertEqual(data["history"][0]["persona_id"], "persona1")

    def test_load_derives_properties(self):
        """Test that properties are correctly derived from history after loading."""
        history = [
            {
                "persona_id": "persona1",
                "session_id": "session1",
                "pr_number": 123,
                "created_at": "2026-01-12T10:00:00Z",
            },
            {
                "persona_id": "persona0",
                "session_id": "session0",
                "pr_number": 122,
                "created_at": "2026-01-12T09:00:00Z",
            },
        ]
        with self.test_path.open("w") as f:
            json.dump({"history": history}, f)

        state = PersistentCycleState.load(self.test_path)

        self.assertEqual(state.last_persona_id, "persona1")
        self.assertEqual(state.last_session_id, "session1")
        self.assertEqual(state.last_pr_number, 123)
        self.assertEqual(len(state.history), 2)

    def test_load_legacy_format(self):
        """Test that it can still load the old format (backwards compatibility)."""
        legacy_data = {
            "last_persona_id": "persona1",
            "last_persona_index": 0,
            "last_session_id": "session1",
            "last_pr_number": 123,
            "updated_at": "2026-01-12T10:00:00Z",
            "history": [
                {
                    "persona_id": "persona1",
                    "session_id": "session1",
                    "pr_number": 123,
                    "created_at": "2026-01-12T10:00:00Z",
                }
            ],
        }
        with self.test_path.open("w") as f:
            json.dump(legacy_data, f)

        state = PersistentCycleState.load(self.test_path)

        self.assertEqual(state.last_persona_id, "persona1")
        self.assertEqual(state.last_session_id, "session1")
        self.assertEqual(len(state.history), 1)

    def test_update_pr_number(self):
        """Test that update_pr_number updates the first entry in history."""
        state = PersistentCycleState()
        state.record_session("persona1", 0, "session1", None)

        state.update_pr_number(456)

        self.assertEqual(state.last_pr_number, 456)
        self.assertEqual(state.history[0]["pr_number"], 456)


class TestCommitCycleState(unittest.TestCase):
    @patch("jules.github.GitHubClient")
    @patch("builtins.open", new_callable=MagicMock)
    def test_commit_cycle_state_only_jules_branch(self, mock_open_func, mock_client_class):
        """Test that commit_cycle_state only calls create_or_update_file for the jules branch."""
        mock_client = mock_client_class.return_value
        mock_client.token = "fake-token"  # noqa: S105
        mock_client.get_file_contents.return_value = {"sha": "fake-sha"}
        mock_client.create_or_update_file.return_value = True

        # Mock file reading
        mock_open_func.return_value.__enter__.return_value.read.return_value = '{"history": []}'

        from jules.scheduler import JULES_BRANCH

        result = commit_cycle_state(Path("fake/path"), "fake message")

        self.assertTrue(result)
        # Should be called exactly once for JULES_BRANCH
        self.assertEqual(mock_client.create_or_update_file.call_count, 1)

        _args, kwargs = mock_client.create_or_update_file.call_args
        self.assertEqual(kwargs["branch"], JULES_BRANCH)

        # Verify it was NOT called for 'main'
        for call in mock_client.create_or_update_file.call_args_list:
            self.assertNotEqual(call.kwargs["branch"], "main")


if __name__ == "__main__":
    unittest.main()
