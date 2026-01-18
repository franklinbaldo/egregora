import pytest
from unittest.mock import MagicMock, patch
from repo.features.mail_handler import MailHandler

@pytest.fixture
def mock_backend():
    with patch("repo.features.mail_handler._get_backend") as mock:
        yield mock.return_value

@pytest.fixture
def mock_gh_client():
    with patch("repo.features.mail_handler.GitHubClient") as mock:
        yield mock.return_value

@pytest.fixture
def handler(mock_gh_client, mock_backend):
    return MailHandler(owner="test-owner", repo="test-repo")

def test_sync_local_to_github(handler, mock_backend, mock_gh_client):
    # Setup: 1 unsynced message for franklin, 1 for the email
    def mock_list_inbox(user_id, unread_only=False):
        if user_id == "franklin":
            return [{"key": "1", "subject": "Subj1", "from_id": "artisan", "body": "Body1", "date": "today"}]
        elif user_id == "franklinbaldo@gmail.com":
            return [{"key": "2", "subject": "Subj2", "from_id": "bolt", "body": "Body2", "date": "today"}]
        return []

    mock_backend.list_inbox.side_effect = mock_list_inbox
    mock_backend.list_tags.return_value = []
    mock_gh_client.create_issue.return_value = {"number": 123}

    # Execute
    handler.sync_local_to_github()

    # Verify
    assert mock_gh_client.create_issue.call_count == 2
    mock_backend.tag_add.assert_any_call("franklin", "1", "synced-to-github")
    mock_backend.tag_add.assert_any_call("franklinbaldo@gmail.com", "2", "synced-to-github")

def test_sync_github_to_local(handler, mock_backend, mock_gh_client):
    # Setup: 1 synced message for franklin only
    def mock_list_inbox(user_id, unread_only=False):
        if user_id == "franklin":
            return [{"key": "1", "subject": "Test Subj", "from_id": "artisan", "body": "Test Body", "date": "today"}]
        return []
    
    mock_backend.list_inbox.side_effect = mock_list_inbox
    mock_backend.list_tags.return_value = ["synced-to-github", "issue-123"]
    
    # Mock GitHub comment
    mock_gh_client.list_issue_comments.return_value = [
        {
            "id": 999,
            "user": {"login": "franklin_user"},
            "body": "This is a reply"
        }
    ]

    with patch("repo.features.mail_handler.send_message") as mock_send:
        # Execute
        handler.sync_github_to_local()

        # Verify
        # It should call send_message only for the 'franklin' identity
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert kwargs["to_id"] == "artisan"
        assert kwargs["subject"] == "Re: Test Subj"
        assert "This is a reply" in kwargs["body"]
        assert kwargs["from_id"] == "franklin"
        
        # Verify tag added to avoid duplicate delivery
        mock_backend.tag_add.assert_called_with("franklin", "1", "replied-comment-999")
