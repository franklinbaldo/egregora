from unittest.mock import Mock, patch

import httpx
import pytest
from repo.core.client import TeamClient, _request_with_retry
from tenacity import RetryError


class TestTeamClientRefactor:
    @pytest.fixture
    def client(self):
        return TeamClient(api_key="test-key")

    @patch("httpx.get")
    def test_request_with_retry_success(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response

        headers = {"X-Goog-Api-Key": "test"}

        # Test direct call to helper (which we will refactor to use tenacity)
        response = _request_with_retry("GET", "http://test.com", headers)

        assert response == mock_response
        assert mock_get.call_count == 1

    @patch("httpx.get")
    def test_request_with_retry_failure_then_success(self, mock_get):
        # Fail twice, then succeed
        success_response = Mock()
        success_response.raise_for_status.return_value = None

        mock_get.side_effect = [
            httpx.ConnectTimeout("Timeout"),
            httpx.ReadTimeout("Timeout"),
            success_response,
        ]

        headers = {"X-Goog-Api-Key": "test"}

        response = _request_with_retry("GET", "http://test.com", headers)

        assert response == success_response
        assert mock_get.call_count == 3

    @patch("httpx.get")
    def test_request_with_retry_exhausted(self, mock_get):
        # Always fail
        mock_get.side_effect = httpx.ConnectTimeout("Timeout")

        headers = {"X-Goog-Api-Key": "test"}

        with pytest.raises((RetryError, httpx.ConnectTimeout)):
            # Tenacity raises RetryError wrapping the original exception
            # Or allows the exception to bubble up depending on config.
            # We want it to bubble up or wrap in TeamClientError eventually.
            _request_with_retry("GET", "http://test.com", headers)

        assert mock_get.call_count >= 3

    @patch("repo.core.client._request_with_retry")
    def test_client_methods_use_retry(self, mock_request, client):
        mock_response = Mock()
        mock_response.json.return_value = {"name": "sessions/123"}
        mock_request.return_value = mock_response

        client.create_session("prompt", "owner", "repo")

        assert mock_request.called

    def test_team_client_error_wrapping(self):
        """Ensure client methods wrap exceptions in TeamClientError (to be implemented)."""
        # To be added after initial refactor

    @patch("repo.core.client._request_with_retry")
    def test_get_activities_without_filter(self, mock_request, client):
        """Test get_activities without createTime filter."""
        mock_response = Mock()
        mock_response.json.return_value = {"activities": []}
        mock_request.return_value = mock_response

        client.get_activities("sessions/abc123")

        mock_request.assert_called_once()
        url = mock_request.call_args[0][1]
        assert "createTime" not in url
        assert "/sessions/abc123/activities" in url

    @patch("repo.core.client._request_with_retry")
    def test_get_activities_with_create_time_filter(self, mock_request, client):
        """Test get_activities with createTime filter (Jan 2026 API)."""
        mock_response = Mock()
        mock_response.json.return_value = {"activities": []}
        mock_request.return_value = mock_response

        timestamp = "2026-01-15T10:30:00.000Z"
        client.get_activities("sessions/abc123", create_time_after=timestamp)

        mock_request.assert_called_once()
        url = mock_request.call_args[0][1]
        assert f"createTime={timestamp}" in url

    @patch("repo.core.client._request_with_retry")
    def test_get_activities_strips_sessions_prefix(self, mock_request, client):
        """Test get_activities properly strips 'sessions/' prefix from ID."""
        mock_response = Mock()
        mock_response.json.return_value = {"activities": []}
        mock_request.return_value = mock_response

        client.get_activities("sessions/abc123")

        url = mock_request.call_args[0][1]
        # Should have /sessions/abc123/ not /sessions/sessions/abc123/
        assert "/sessions/abc123/activities" in url
        assert "/sessions/sessions/" not in url
