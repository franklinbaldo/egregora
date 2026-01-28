"""Unit tests for the email polling module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add .team to path so we can import repo.features
REPO_ROOT = Path(__file__).parents[3]
TEAM_PATH = REPO_ROOT / ".team"
if str(TEAM_PATH) not in sys.path:
    sys.path.append(str(TEAM_PATH))

from repo.features.polling import EmailPoller, get_latest_activity_timestamp  # noqa: E402


class TestGetLatestActivityTimestamp:
    """Tests for the get_latest_activity_timestamp helper function."""

    def test_empty_activities_returns_none(self):
        """Empty activity list returns None."""
        result = get_latest_activity_timestamp([])
        assert result is None

    def test_single_activity_returns_its_timestamp(self):
        """Single activity returns its createTime."""
        activities = [{"name": "activity-1", "createTime": "2026-01-15T10:30:00.000Z"}]
        result = get_latest_activity_timestamp(activities)
        assert result == "2026-01-15T10:30:00.000Z"

    def test_multiple_activities_returns_latest(self):
        """Multiple activities return the latest createTime."""
        activities = [
            {"name": "activity-1", "createTime": "2026-01-15T10:30:00.000Z"},
            {"name": "activity-2", "createTime": "2026-01-15T12:00:00.000Z"},
            {"name": "activity-3", "createTime": "2026-01-15T11:00:00.000Z"},
        ]
        result = get_latest_activity_timestamp(activities)
        assert result == "2026-01-15T12:00:00.000Z"

    def test_activities_without_createtime_are_ignored(self):
        """Activities missing createTime are ignored."""
        activities = [
            {"name": "activity-1"},
            {"name": "activity-2", "createTime": "2026-01-15T10:30:00.000Z"},
        ]
        result = get_latest_activity_timestamp(activities)
        assert result == "2026-01-15T10:30:00.000Z"

    def test_all_activities_without_createtime_returns_none(self):
        """All activities missing createTime returns None."""
        activities = [{"name": "activity-1"}, {"name": "activity-2"}]
        result = get_latest_activity_timestamp(activities)
        assert result is None


class TestEmailPollerTimestampFiltering:
    """Tests for the EmailPoller timestamp-based filtering."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock TeamClient."""
        client = MagicMock()
        client.list_sessions.return_value = {"sessions": []}
        client.get_activities.return_value = {"activities": []}
        return client

    @pytest.fixture
    def poller(self, mock_client):
        """Create an EmailPoller with mock client."""
        return EmailPoller(mock_client)

    def test_initial_poll_has_no_timestamp_filter(self, poller, mock_client):
        """First poll for a session has no createTime filter."""
        mock_client.list_sessions.return_value = {
            "sessions": [{"name": "sessions/abc123", "state": "IN_PROGRESS"}]
        }
        mock_client.get_activities.return_value = {"activities": []}

        poller.poll_and_deliver()

        # First poll should not have create_time_after
        mock_client.get_activities.assert_called_once_with(
            "sessions/abc123",
            create_time_after=None,
        )

    def test_subsequent_poll_uses_last_timestamp(self, poller, mock_client):
        """Subsequent polls use the last seen timestamp as filter."""
        mock_client.list_sessions.return_value = {
            "sessions": [{"name": "sessions/abc123", "state": "IN_PROGRESS"}]
        }

        # First poll returns activities
        mock_client.get_activities.return_value = {
            "activities": [
                {
                    "name": "activity-1",
                    "createTime": "2026-01-15T10:30:00.000Z",
                    "artifacts": [],
                }
            ]
        }

        poller.poll_and_deliver()

        # Clear the call history
        mock_client.get_activities.reset_mock()

        # Second poll should use the timestamp from first poll
        mock_client.get_activities.return_value = {"activities": []}
        poller.poll_and_deliver()

        mock_client.get_activities.assert_called_once_with(
            "sessions/abc123",
            create_time_after="2026-01-15T10:30:00.000Z",
        )

    def test_timestamp_updates_with_new_activities(self, poller, mock_client):
        """Timestamp is updated when new activities are received."""
        mock_client.list_sessions.return_value = {
            "sessions": [{"name": "sessions/abc123", "state": "IN_PROGRESS"}]
        }

        # First poll
        mock_client.get_activities.return_value = {
            "activities": [
                {
                    "name": "activity-1",
                    "createTime": "2026-01-15T10:00:00.000Z",
                    "artifacts": [],
                }
            ]
        }
        poller.poll_and_deliver()

        # Second poll returns newer activities
        mock_client.get_activities.return_value = {
            "activities": [
                {
                    "name": "activity-2",
                    "createTime": "2026-01-15T12:00:00.000Z",
                    "artifacts": [],
                }
            ]
        }
        poller.poll_and_deliver()

        # Third poll should use the latest timestamp
        mock_client.get_activities.reset_mock()
        mock_client.get_activities.return_value = {"activities": []}
        poller.poll_and_deliver()

        mock_client.get_activities.assert_called_once_with(
            "sessions/abc123",
            create_time_after="2026-01-15T12:00:00.000Z",
        )

    def test_separate_timestamps_per_session(self, poller, mock_client):
        """Each session tracks its own last poll timestamp."""
        mock_client.list_sessions.return_value = {
            "sessions": [
                {"name": "sessions/session-a", "state": "IN_PROGRESS"},
                {"name": "sessions/session-b", "state": "IN_PROGRESS"},
            ]
        }

        # First poll returns different timestamps for each session
        def get_activities_side_effect(session_name, create_time_after=None):
            _ = create_time_after  # Mark as intentionally unused for API compatibility
            if "session-a" in session_name:
                return {
                    "activities": [
                        {
                            "name": "activity-a1",
                            "createTime": "2026-01-15T10:00:00.000Z",
                            "artifacts": [],
                        }
                    ]
                }
            return {
                "activities": [
                    {
                        "name": "activity-b1",
                        "createTime": "2026-01-15T11:00:00.000Z",
                        "artifacts": [],
                    }
                ]
            }

        mock_client.get_activities.side_effect = get_activities_side_effect
        poller.poll_and_deliver()

        # Verify timestamps are tracked separately
        assert poller.last_poll_times["session-a"] == "2026-01-15T10:00:00.000Z"
        assert poller.last_poll_times["session-b"] == "2026-01-15T11:00:00.000Z"
