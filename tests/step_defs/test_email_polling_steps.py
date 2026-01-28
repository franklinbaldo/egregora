from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from repo.core.client import TeamClient
from repo.features.polling import EmailPoller

# Load scenarios
scenarios("../features/email_polling.feature")


@pytest.fixture
def mock_client():
    client = MagicMock(spec=TeamClient)
    # Default responses
    client.list_sessions.return_value = {"sessions": []}
    client.get_activities.return_value = {"activities": []}
    return client


@pytest.fixture
def email_poller(mock_client):
    return EmailPoller(mock_client)


@given(parsers.parse('a session "{session_resource}" exists for "{persona_id}"'))
def session_exists(mock_client, session_resource, persona_id):
    sessions = mock_client.list_sessions.return_value.get("sessions", [])
    sessions.append(
        {
            "name": session_resource,
            "title": f"Session for {persona_id}",
            "state": "COMPLETED",
            "createTime": "2026-01-13T10:00:00Z",
        }
    )
    mock_client.list_sessions.return_value = {"sessions": sessions}


@given(parsers.parse('an active session "{session_resource}" exists for "{persona_id}"'))
def active_session_exists(mock_client, session_resource, persona_id):
    sessions = mock_client.list_sessions.return_value.get("sessions", [])
    sessions.append(
        {
            "name": session_resource,
            "title": f"Active work for {persona_id}",
            "state": "IN_PROGRESS",
            "createTime": "2026-01-13T12:00:00Z",
        }
    )
    mock_client.list_sessions.return_value = {"sessions": sessions}


@when(parsers.parse('a new activity appears in "{session_resource}" with a git patch:'))
def activity_appears(mock_client, session_resource, docstring):
    # Match the session identifier logic in polling.py (it iterates list_sessions)
    # But get_activities is called per session.
    # We need to ensure get_activities returns this patch when called for session_resource

    # Simple mock behavior: if name matches, return the activity
    # Updated to accept create_time_after parameter (Jan 2026 Jules API)
    def side_effect(res_name, create_time_after=None):
        if res_name == session_resource or res_name.split("/")[-1] == session_resource.split("/")[-1]:
            return {
                "activities": [
                    {
                        "name": f"{session_resource}/activities/pulse-1",
                        "createTime": "2026-01-15T10:30:00.000Z",
                        "artifacts": [{"contents": {"changeSet": {"gitPatch": {"unidiffPatch": docstring}}}}],
                    }
                ]
            }
        return {"activities": []}

    # We can't easily use side_effect with get_activities if it's already a MagicMock(spec)
    # Actually we can.
    mock_client.get_activities.side_effect = side_effect


@when("the email poller runs")
def run_poller(email_poller):
    email_poller.poll_and_deliver()


@then(parsers.parse('a message should be sent to session "{session_resource}"'))
def verify_message_sent(mock_client, session_resource):
    # Extract session ID from resource name
    expected_id = session_resource.split("/")[-1]

    # Check calls to send_message(session_id, message)
    found = False
    for call in mock_client.send_message.call_args_list:
        if call.args[0] == expected_id:
            found = True
            break
    assert found, f"Expected message to be sent to session {expected_id}, but wasn't."


@then(parsers.parse('the message content should contain "{text}"'))
def verify_message_content(mock_client, text):
    # Check all messages sent
    all_contents = []
    for call in mock_client.send_message.call_args_list:
        all_contents.append(call.args[1])

    assert any(text in content for content in all_contents), f"None of the sent messages contained '{text}'"


@then("no messages should be sent to any sessions")
def verify_no_messages(mock_client):
    assert mock_client.send_message.call_count == 0
