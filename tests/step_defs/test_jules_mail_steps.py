import sys
import subprocess
from pathlib import Path
from pytest_bdd import given, when, then, scenarios, parsers
import pytest
from typer.testing import CliRunner
from jules.cli.mail import app
from jules.features.mail import send_message, get_message, list_inbox

# Load scenarios
scenarios("../features/jules_mail.feature")

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
    pass # Hanlded by fixture

@given('the file system is isolated')
def isolate_filesystem(isolated_fs):
    pass # Handled by fixture

@given(parsers.parse('a message exists from "{sender}" to "{recipient}" with subject "{subject}"'), target_fixture="message_key")
def create_message_subject(sender, recipient, subject):
    return send_message(sender, recipient, subject, "Body content")

@given(parsers.parse('a message exists from "{sender}" to "{recipient}" with body "{body}"'), target_fixture="message_key")
def create_message_body(sender, recipient, body):
    return send_message(sender, recipient, "Subject", body)

@when(parsers.parse('I run the mail command "{command}" with args:'), target_fixture="last_command_result")
def run_mail_command(runner, command, datatable):
    # Flatten datatable to list of args
    flat_args = [command]
    if datatable:
        for row in datatable:
            # Check if this is a header row and skip it
            if row[0] == 'arg' and row[1] == 'value':
                continue
            
            # pytest-bdd datatable rows are lists of strings
            flat_args.append(str(row[0])) # arg
            flat_args.append(str(row[1])) # value
            
    print(f"DEBUG: Running {flat_args}")
    result = runner.invoke(app, flat_args)
    return result

@when('I run the mail command "read" with the message key', target_fixture="last_command_result")
def run_read_command(runner, message_key):
    return runner.invoke(app, ["read", message_key, "--persona", "me@team"])

@then('the command should exit successfully')
def check_exit_success(last_command_result):
    if last_command_result.exit_code != 0:
        print(f"Command failed: {last_command_result.output}")
    assert last_command_result.exit_code == 0

@then(parsers.parse('a mail file should exist in "{path}"'))
def check_file_exists(isolated_fs, path):
    target_dir = isolated_fs / path
    assert target_dir.exists()
    assert any(target_dir.iterdir())

@then(parsers.parse('the output should contain "{text}"'))
def check_output_contains(last_command_result, text):
    assert text in last_command_result.stdout

@then('the message should be marked as read')
def check_message_read(message_key):
    # We need to know who the recipient was. In the scenario it is "me@team"
    msgs = list_inbox("me@team")
    # Find message
    for m in msgs:
        if m["key"] == message_key:
            assert m["read"] is True
            return
    assert False, "Message not found"
