from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from repo.cli.mail import app
from repo.features.mail import list_inbox, send_message
from typer.testing import CliRunner

# Load scenarios
scenarios("../features/team_mail.feature")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_fs(tmp_path, monkeypatch):
    """Isolate file system for tests."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JULES_MAIL_STORAGE", "local")
    return tmp_path


@given('the mail backend is set to "local"')
def set_local_backend(isolated_fs):
    pass  # Hanlded by fixture


@given("the file system is isolated")
def isolate_filesystem(isolated_fs):
    pass  # Handled by fixture


@given(
    parsers.parse('a message exists from "{sender}" to "{recipient}" with subject "{subject}"'),
    target_fixture="message_key",
)
def create_message_subject(sender, recipient, subject):
    return send_message(sender, recipient, subject, "Body content")


@given(
    parsers.parse('a message exists from "{sender}" to "{recipient}" with body "{body}"'),
    target_fixture="message_key",
)
def create_message_body(sender, recipient, body):
    return send_message(sender, recipient, "Subject", body)


@given(parsers.parse('personas "{names}" exist'))
def create_personas(isolated_fs, names):
    # names string like '"alice", "bob"' -> parse
    # simplified parsing logic
    # extract words inside quotes or just split
    clean_names = [n.strip().replace('"', "") for n in names.split(",")]
    for name in clean_names:
        (isolated_fs / f".team/personas/{name}").mkdir(parents=True, exist_ok=True)


@when(parsers.parse('I run the mail command "{command}" with args:'), target_fixture="last_command_result")
def run_mail_command(runner, command, datatable):
    # Flatten datatable to list of args
    flat_args = [command]
    if datatable:
        for row in datatable:
            # Check if this is a header row and skip it
            if row[0] == "arg" and row[1] == "value":
                continue

            # pytest-bdd datatable rows are lists of strings
            flat_args.append(str(row[0]))  # arg
            flat_args.append(str(row[1]))  # value

    with patch("repo.features.session.SessionManager") as mock_sm_class:
        # Mock active session for authentication
        mock_sm = MagicMock()
        mock_sm.get_active_persona.return_value = "tester"
        mock_sm.get_active_sequence.return_value = "seq-1"
        mock_sm_class.return_value = mock_sm

        return runner.invoke(app, flat_args)


@when('I run the mail command "read" with the message key', target_fixture="last_command_result")
def run_read_command(runner, message_key):
    with patch("repo.features.session.SessionManager") as mock_sm_class:
        # Mock active session for authentication
        mock_sm = MagicMock()
        mock_sm.get_active_persona.return_value = "tester"
        mock_sm.get_active_sequence.return_value = "seq-1"
        mock_sm_class.return_value = mock_sm

        return runner.invoke(app, ["read", message_key, "--persona", "me@team"])


@then("the command should exit successfully")
def check_exit_success(last_command_result):
    if last_command_result.exit_code != 0:
        pass
    assert last_command_result.exit_code == 0


@then(parsers.parse('a mail file should exist in "{path}"'))
def check_file_exists(isolated_fs, path):
    # This step was checking for explicit Maildir paths like .../mail/new
    # With MH, we have a single .team/mail directory and shared messages.
    # We should interpret the path check as verifying *some* mail exists for the persona
    # OR we need to update the Feature file to be less implementation specific.
    # The feature file says: And a mail file should exist in ".team/personas/curator@team/mail/new"

    # We will relax this check to verify that the message is listed in the inbox via API
    # instead of checking filesystem path.
    # Extract persona from path if possible, or assume based on scenario.

    # Actually, the Scenario explicitly lists a path. We should probably update the SCENARIO
    # to be behavior driven, but the plan step says "Refactor Existing Integration Tests...
    # Remove filesystem assertions... Replace with behavior checks".

    # However, if I can't change the feature file easily (I can, it's in the repo),
    # I should change the feature file steps to be behavior driven.
    # "Then the message should be delivered to curator@team"

    # But since I am here in step definitions, I can map the old step string to a new check.
    # path string is like ".team/personas/alice/mail/new"

    parts = path.split("/")
    # Try to find persona name. It's usually after 'personas'
    try:
        idx = parts.index("personas")
        persona = parts[idx + 1]
        # Verify inbox has messages
        assert len(list_inbox(persona)) > 0
    except ValueError:
        # Fallback: check if the root mail dir has content
        # MH stores files in .team/mail
        mail_root = isolated_fs / ".team/mail"
        assert mail_root.exists()
        assert any(p.name.isdigit() for p in mail_root.iterdir())


@then(parsers.parse('the output should contain "{text}"'))
def check_output_contains(last_command_result, text):
    assert text in last_command_result.stdout


@then("the message should be marked as read")
def check_message_read(message_key):
    # We need to know who the recipient was. In the scenario it is "me@team"
    msgs = list_inbox("me@team")
    # Find message
    for m in msgs:
        if m["key"] == message_key:
            assert m["read"] is True
            return
    msg = "Message not found"
    raise AssertionError(msg)
