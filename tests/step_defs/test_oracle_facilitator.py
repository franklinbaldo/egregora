from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenario, then, when


# Define the scenario specifically for this test file
@scenario("../features/oracle_facilitator.feature", "Unblocking a session awaiting user feedback")
def test_unblocking_session():
    pass


@scenario("../features/oracle_facilitator.feature", "Delivering Oracle response back to the session")
def test_delivering_oracle_response():
    pass


@pytest.fixture
def mock_jules_client(mocker):
    # Mock TeamClient in engine.py
    mock_client = mocker.Mock()
    mocker.patch("repo.scheduler.engine.TeamClient", return_value=mock_client)
    return mock_client


@pytest.fixture
def mock_mail_features(mocker):
    # Mock mail features in engine.py
    return {
        "send": mocker.patch("repo.scheduler.engine.send_message"),
        "inbox": mocker.patch("repo.scheduler.engine.list_inbox"),
        "get": mocker.patch("repo.scheduler.engine.get_message"),
        "read": mocker.patch("repo.scheduler.engine.mark_read"),
    }


@given(parsers.parse('a session for persona "{persona}" is in state "AWAITING_USER_FEEDBACK"'))
def session_awaiting_feedback(persona, mock_jules_client):
    mock_jules_client.list_sessions.return_value = {
        "sessions": [
            {
                "name": "sessions/123",
                "title": f"🛠️ {persona}: some task",
                "state": "AWAITING_USER_FEEDBACK",
                "createTime": "2026-01-15T00:00:00Z",
            }
        ]
    }
    # Also need to mock list_inbox for oracle to avoid errors in facilitator loop
    # We'll set a default empty inbox
    # Wait, mock_mail_features will handle it if it's called after


@given(parsers.parse('the session has a pending question "{question}"'))
def session_has_question(question, mock_jules_client):
    mock_jules_client.get_activities.return_value = {
        "activities": [{"type": "MESSAGE", "message": {"text": question, "role": "AGENT"}}]
    }


@given(parsers.parse('there is a mail from "oracle" to "{persona}" with content "{content}"'))
def oracle_mail_exists(persona, content, mock_mail_features):
    mock_mail_features["inbox"].return_value = [
        {"key": "msg_456", "from": "oracle", "subject": f"Reply to {persona}", "read": False}
    ]
    mock_mail_features["get"].return_value = {
        "key": "msg_456",
        "from": "oracle",
        "to": persona,
        "subject": f"Reply to {persona}",
        "body": content,
        "date": "2026-01-15T00:05:00Z",
    }


@when("the scheduler runs the facilitator tick")
def run_facilitator_tick(mock_mail_features):
    # If not already set by oracle_mail_exists, ensure inbox is empty
    if mock_mail_features["inbox"].return_value is None or isinstance(
        mock_mail_features["inbox"].return_value, MagicMock
    ):
        mock_mail_features["inbox"].return_value = []

    from repo.scheduler.engine import execute_facilitator_tick

    # Mock execute_single_persona to prevent Oracle session creation side effects
    with patch("repo.scheduler.engine.execute_single_persona"):
        execute_facilitator_tick(dry_run=False)


@then(parsers.parse('a mail from "facilitator" should be sent to "oracle"'))
def mail_sent_to_oracle(mock_mail_features):
    assert mock_mail_features["send"].called
    found = False
    for call in mock_mail_features["send"].call_args_list:
        if call.args[1] == "oracle":
            found = True
            break
    assert found


@then(parsers.parse('the mail subject should contain "Help requested for {persona}"'))
def mail_subject_contains(persona, mock_mail_features):
    subjects = [
        call.args[2] for call in mock_mail_features["send"].call_args_list if call.args[1] == "oracle"
    ]
    assert any(persona in s for s in subjects)


@then(parsers.parse('the mail body should contain "{question}"'))
def mail_body_contains(question, mock_mail_features):
    bodies = [call.args[3] for call in mock_mail_features["send"].call_args_list if call.args[1] == "oracle"]
    assert any(question in b for b in bodies)


@then(parsers.parse('the message "{content}" should be sent to the "{persona}" session'))
def message_sent_to_session(content, persona, mock_jules_client):
    mock_jules_client.send_message.assert_called_with("123", content)


@then(parsers.parse('the mail from "oracle" to "{persona}" should be marked as read'))
def mail_marked_read(persona, mock_mail_features):
    mock_mail_features["read"].assert_called_with(persona, "msg_456")
