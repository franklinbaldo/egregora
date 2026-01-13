import pytest
import httpx
from unittest.mock import Mock, patch
from jules.client import JulesClient, _request_with_retry
from jules.exceptions import JulesClientError
from tenacity import RetryError

class TestJulesClientRefactor:

    @pytest.fixture
    def client(self):
        return JulesClient(api_key="test-key")

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
            success_response
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
            # We want it to bubble up or wrap in JulesClientError eventually.
            _request_with_retry("GET", "http://test.com", headers)

        assert mock_get.call_count >= 3

    @patch("jules.client._request_with_retry")
    def test_client_methods_use_retry(self, mock_request, client):
        mock_response = Mock()
        mock_response.json.return_value = {"name": "sessions/123"}
        mock_request.return_value = mock_response

        client.create_session("prompt", "owner", "repo")

        assert mock_request.called

    def test_jules_client_error_wrapping(self):
        """Ensure client methods wrap exceptions in JulesClientError (to be implemented)."""
        pass # To be added after initial refactor
