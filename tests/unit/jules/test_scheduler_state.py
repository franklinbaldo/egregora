import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

# Add .jules to path
REPO_ROOT = Path(__file__).parents[3]
JULES_PATH = REPO_ROOT / ".jules"
if str(JULES_PATH) not in sys.path:
    sys.path.append(str(JULES_PATH))

from jules.scheduler.state import PersistentCycleState, commit_cycle_state  # noqa: E402


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
        self.assertIsInstance(data["history"], dict)
        self.assertEqual(len(data["history"]), 1)
        self.assertEqual(data["history"]["0"]["persona_id"], "persona1")

    def test_load_derives_properties(self):
        """Test that properties are correctly derived from history after loading."""
        history = {
            "0": {
                "persona_id": "persona0",
                "session_id": "session0",
                "pr_number": 122,
                "created_at": "2026-01-12T09:00:00Z",
            },
            "1": {
                "persona_id": "persona1",
                "session_id": "session1",
                "pr_number": 123,
                "created_at": "2026-01-12T10:00:00Z",
            },
        }
        with self.test_path.open("w") as f:
            json.dump({"history": history}, f)

        state = PersistentCycleState.load(self.test_path)

        self.assertEqual(state.persona_id, "persona1")
        self.assertEqual(state.session_id, "session1")
        self.assertEqual(state.pr_number, 123)
        self.assertEqual(len(state.history), 2)

    def test_load_legacy_format(self):
        """Test that it can still load the old format (backwards compatibility)."""
        # In legacy list, history[0] is the NEWEST.
        legacy_data = {
            "history": [
                {
                    "persona_id": "newest",
                    "session_id": "s2",
                    "created_at": "2026-01-12T10:00:00Z",
                },
                {
                    "persona_id": "oldest",
                    "session_id": "s1",
                    "created_at": "2026-01-12T09:00:00Z",
                },
            ],
        }
        with self.test_path.open("w") as f:
            json.dump(legacy_data, f)

        state = PersistentCycleState.load(self.test_path)

        # reversed([newest, oldest]) -> [oldest, newest]
        # index 0 -> oldest, index 1 -> newest
        # persona_id (highest index) -> newest
        self.assertEqual(state.persona_id, "newest")
        self.assertEqual(len(state.history), 2)
        self.assertEqual(state.history["1"]["persona_id"], "newest")
        self.assertEqual(state.history["0"]["persona_id"], "oldest")

    def test_update_pr_number(self):
        """Test that update_pr_number updates the latest entry in history."""
        state = PersistentCycleState()
        state.record_session("persona1", 0, "session1", None)
        state.record_session("persona2", 1, "session2", None)

        state.update_pr_number(456)

        self.assertEqual(state.pr_number, 456)
        self.assertEqual(state.history["1"]["pr_number"], 456)

    def test_sequential_keys(self):
        """Test that keys are sequential integers."""
        state = PersistentCycleState()
        state.record_session("p1", 0, "s1")
        state.record_session("p2", 1, "s2")

        self.assertIn("0", state.history)
        self.assertIn("1", state.history)
        self.assertEqual(state.history["0"]["persona_id"], "p1")
        self.assertEqual(state.history["1"]["persona_id"], "p2")

    def test_save_sorts_history_keys(self):
        """Test that history keys are sorted as integers when saved."""
        state = PersistentCycleState()
        # Add out of order
        state.history["10"] = {"persona_id": "p10"}
        state.history["2"] = {"persona_id": "p2"}
        state.history["1"] = {"persona_id": "p1"}

        state.save(self.test_path)

        with self.test_path.open() as f:
            data = json.load(f)

        keys = list(data["history"].keys())
        self.assertEqual(keys, ["1", "2", "10"])

    def test_load_with_track_state_legacy_prefix(self):
        """Test loading with legacy 'last_' prefix in track state."""
        legacy_track_data = {
            "default": {
                "last_persona_id": "old_persona",
                "last_session_id": "old_session",
                "last_pr_number": 99,
                "updated_at": "2026-01-11T08:00:00Z",
            }
        }
        with self.test_path.open("w") as f:
            json.dump({"history": {}, "tracks": legacy_track_data}, f)

        state = PersistentCycleState.load(self.test_path)
        track = state.get_track("default")

        self.assertEqual(track.persona_id, "old_persona")
        self.assertEqual(track.session_id, "old_session")
        self.assertEqual(track.pr_number, 99)
        self.assertIsInstance(track.updated_at, datetime)


class TestCommitCycleState(unittest.TestCase):
    @patch("jules.core.github.GitHubClient")
    @patch("builtins.open", new_callable=MagicMock)
    def test_commit_cycle_state_only_jules_branch(self, mock_open_func, mock_client_class):
        """Test that commit_cycle_state only calls create_or_update_file for the jules branch."""
        mock_client = mock_client_class.return_value
        mock_client.token = "fake-token"  # noqa: S105
        mock_client.get_file_contents.return_value = {"sha": "fake-sha"}
        mock_client.create_or_update_file.return_value = True

        # Mock file reading
        mock_open_func.return_value.__enter__.return_value.read.return_value = '{"history": {}}'

        from jules.scheduler.legacy import JULES_BRANCH

        result = commit_cycle_state(Path("fake/path"), "fake message")

        self.assertTrue(result)
        # Should be called exactly once for JULES_BRANCH
        self.assertEqual(mock_client.create_or_update_file.call_count, 1)

        _args, kwargs = mock_client.create_or_update_file.call_args
        self.assertEqual(kwargs["branch"], JULES_BRANCH)


if __name__ == "__main__":
    unittest.main()
