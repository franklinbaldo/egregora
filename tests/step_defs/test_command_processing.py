import pytest
from pytest_bdd import given, parsers, scenario, then, when

from egregora.agents.commands import (
    command_to_announcement,
    extract_commands,
    filter_commands,
    is_command,
    parse_command,
)
from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import DocumentType


# Fixtures
@pytest.fixture
def context():
    return {}


# Scenarios
@scenario("../features/command_processing.feature", "Detect valid Egregora commands")
def test_detect_valid_commands():
    pass


@scenario("../features/command_processing.feature", "Case-insensitive command detection")
def test_detect_commands_case_insensitively():
    pass


@scenario("../features/command_processing.feature", "Ignoring regular messages")
def test_ignore_regular_messages():
    pass


@scenario("../features/command_processing.feature", "Parsing an avatar command")
def test_parse_avatar_command():
    pass


@scenario("../features/command_processing.feature", "Parsing a bio command")
def test_parse_bio_command():
    pass


@scenario("../features/command_processing.feature", "Parsing an interests command")
def test_parse_interests_command():
    pass


@scenario("../features/command_processing.feature", "Parsing an unknown command")
def test_parse_unknown_command():
    pass


@scenario("../features/command_processing.feature", "Filtering commands from a message list")
def test_filter_commands():
    pass


@scenario("../features/command_processing.feature", "Extracting commands from a message list")
def test_extract_commands():
    pass


@scenario("../features/command_processing.feature", "Generating an announcement for an avatar update")
def test_generate_announcement_for_avatar_update():
    pass


@scenario("../features/command_processing.feature", "Generating an announcement for a bio update")
def test_generate_announcement_for_bio_update():
    pass


@scenario("../features/command_processing.feature", "Generating an announcement for an interests command")
def test_generate_announcement_for_interests_update():
    pass


# Given steps
@given("a message containing a valid command", target_fixture="context")
def valid_command_message():
    return {"message": "/egregora avatar set https://example.com/avatar.jpg"}


@given(parsers.parse('a message containing the command "{command_text}"'), target_fixture="context")
def given_a_message_with_command_text(command_text):
    return {"message": command_text}


@given("a message that is not a command", target_fixture="context")
def regular_message():
    return {"message": "This is a regular message"}


@given(parsers.parse('a message with the avatar command "{command}"'), target_fixture="context")
def avatar_command_message(command):
    return {"message": command}


@given(parsers.parse('a message with the bio command "{command}"'), target_fixture="context")
def bio_command_message(command):
    return {"message": command}


@given(parsers.parse('a message with the interests command "{command}"'), target_fixture="context")
def interests_command_message(command):
    return {"message": command}


@given(parsers.parse('a message with the unknown command "{command}"'), target_fixture="context")
def unknown_command_message(command):
    return {"message": command}


@given("a list of messages containing both commands and regular text", target_fixture="context")
def mixed_message_list():
    messages = [
        {"text": "Regular message 1", "author": "john"},
        {"text": "/egregora avatar set https://...", "author": "alice"},
        {"text": "Regular message 2", "author": "bob"},
        {"text": "/egregora bio I am a researcher", "author": "alice"},
        {"text": "Regular message 3", "author": "john"},
    ]
    return {"messages": messages}


@given("a user command message for an avatar update", target_fixture="context")
def user_command_avatar_update():
    return {
        "message": {
            "text": "/egregora avatar set https://example.com/avatar.jpg",
            "author_uuid": "john-uuid",
            "author_name": "John Doe",
            "timestamp": "2025-03-07T10:00:00",
        }
    }


@given("a user command message for a bio update", target_fixture="context")
def user_command_bio_update():
    return {
        "message": {
            "text": "/egregora bio I am an AI researcher",
            "author_uuid": "alice-uuid",
            "author_name": "Alice",
            "timestamp": "2025-03-07T11:00:00",
        }
    }


@given("a user command message for an interests update", target_fixture="context")
def user_command_interests_update():
    return {
        "message": {
            "text": "/egregora interests AI, ethics, philosophy",
            "author_uuid": "bob-uuid",
            "author_name": "Bob",
            "timestamp": "2025-03-07T12:00:00",
        }
    }


# When steps
@when("the system checks if it is a command", target_fixture="context")
def check_if_command(context):
    context["is_command"] = is_command(context["message"])
    return context


@when("the system parses the command", target_fixture="context")
def parse_the_command(context):
    context["parsed_command"] = parse_command(context["message"])
    return context


@when("the system filters out the command messages", target_fixture="context")
def filter_out_commands(context):
    context["filtered_messages"] = filter_commands(context["messages"])
    return context


@when("the system extracts the command messages", target_fixture="context")
def extract_the_commands(context):
    context["extracted_commands"] = extract_commands(context["messages"])
    return context


@when("the system generates an announcement from the command", target_fixture="context")
def generate_announcement(context):
    context["announcement"] = command_to_announcement(context["message"])
    return context


# Then steps
@then("it should be identified as a command")
def is_identified_as_command(context):
    assert context["is_command"] is True


@then("it should not be identified as a command")
def is_not_identified_as_command(context):
    assert context["is_command"] is False


@then(parsers.parse('the command type should be "{command_type}"'))
def check_command_type(context, command_type):
    assert context["parsed_command"]["type"] == command_type


@then(parsers.parse('the action should be "{action}"'))
def check_action(context, action):
    assert context["parsed_command"]["action"] == action


@then(parsers.parse('the URL parameter should contain "{url}"'))
def check_url_parameter(context, url):
    assert url in context["parsed_command"]["params"]["url"]


@then(parsers.parse('the bio parameter should contain "{bio}"'))
def check_bio_parameter(context, bio):
    assert bio in context["parsed_command"]["params"]["bio"]


@then(parsers.parse('the interests parameter should contain "{interests}"'))
def check_interests_parameter(context, interests):
    assert interests in context["parsed_command"]["params"]["interests"]


@then(parsers.parse('the raw parameters should contain "{raw_params}"'))
def check_raw_parameters(context, raw_params):
    assert raw_params in context["parsed_command"]["params"]["raw"]


@then("the resulting list should only contain regular messages")
def check_filtered_list(context):
    assert len(context["filtered_messages"]) == 3
    assert all("/egregora" not in m["text"].lower() for m in context["filtered_messages"])


@then("the resulting list should only contain command messages")
def check_extracted_list(context):
    assert len(context["extracted_commands"]) == 2
    assert all("/egregora" in m["text"].lower() for m in context["extracted_commands"])


@then("an ANNOUNCEMENT document should be created")
def check_announcement_document_created(context):
    assert context["announcement"].type == DocumentType.ANNOUNCEMENT


@then(parsers.parse('the document\'s event type should be "{event_type}"'))
def check_event_type(context, event_type):
    assert context["announcement"].metadata["event_type"] == event_type


@then("the document should be authored by Egregora")
def check_egregora_authorship(context):
    assert context["announcement"].metadata["authors"][0]["uuid"] == EGREGORA_UUID
    assert context["announcement"].metadata["authors"][0]["name"] == EGREGORA_NAME


@then(parsers.parse('the document\'s actor should be "{actor_uuid}"'))
def check_document_actor(context, actor_uuid):
    assert context["announcement"].metadata["actor"] == actor_uuid


@then("the document's content should mention the user and the avatar update")
def check_avatar_announcement_content(context):
    assert "John Doe" in context["announcement"].content
    assert "avatar" in context["announcement"].content.lower()


@then("the document's content should contain the new bio text")
def check_bio_announcement_content(context):
    assert "I am an AI researcher" in context["announcement"].content


@then("the document's content should contain the new interests")
def check_interests_announcement_content(context):
    assert "AI, ethics, philosophy" in context["announcement"].content
