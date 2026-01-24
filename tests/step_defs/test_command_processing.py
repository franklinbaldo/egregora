"""Step definitions for command_processing.feature."""

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from egregora.agents.commands import (
    command_to_announcement,
    extract_commands,
    filter_commands,
    is_command,
    parse_command,
)
from egregora.data_primitives.document import DocumentType
from egregora.knowledge.constants import EGREGORA_NAME, EGREGORA_UUID

# Scenarios


@scenario("../features/command_processing.feature", "Parsing an avatar command")
def test_parsing_avatar_command():
    pass


@scenario("../features/command_processing.feature", "Parsing a bio command")
def test_parsing_bio_command():
    pass


@scenario("../features/command_processing.feature", "Parsing an interests command")
def test_parsing_interests_command():
    pass


@scenario("../features/command_processing.feature", "Ignoring regular messages")
def test_ignoring_regular_messages():
    pass


@scenario(
    "../features/command_processing.feature",
    "Case-insensitive command detection",
)
def test_case_insensitive_command_detection():
    pass


@scenario(
    "../features/command_processing.feature",
    "Filtering commands from a message list",
)
def test_filtering_commands_from_message_list():
    pass


@scenario(
    "../features/command_processing.feature",
    "Extracting commands from a message list",
)
def test_extracting_commands_from_message_list():
    pass


@scenario(
    "../features/command_processing.feature",
    "Generating an announcement for an avatar update",
)
def test_generating_announcement_for_avatar_update():
    pass


@scenario(
    "../features/command_processing.feature",
    "Generating an announcement for a bio update",
)
def test_generating_announcement_for_bio_update():
    pass


@scenario(
    "../features/command_processing.feature",
    "Generating an announcement for an interests command",
)
def test_generating_announcement_for_interests_command():
    pass


# Fixtures


@pytest.fixture
def context():
    """Provides a dictionary for sharing state between steps."""
    return {}


# Given Steps


@given("a list of messages with and without commands", target_fixture="messages")
def list_of_messages():
    return [
        {"text": "Regular message 1", "author": "john"},
        {"text": "/egregora avatar set https://...", "author": "alice"},
        {"text": "Regular message 2", "author": "bob"},
        {"text": "/egregora bio I am a researcher", "author": "alice"},
        {"text": "Regular message 3", "author": "john"},
    ]


@given("a message containing a valid command", target_fixture="context")
def valid_command_message():
    return {"message": "/egregora avatar set https://example.com/avatar.jpg"}


@given(parsers.parse('a message containing the command "{command_text}"'), target_fixture="context")
def message_with_command_text(command_text):
    return {"message": command_text}


@given("a message that is not a command", target_fixture="context")
def not_a_command_message():
    return {"message": "This is a regular message"}


@given(parsers.parse('a message with the avatar command "{command}"'), target_fixture="context")
def message_with_avatar_command(command):
    return {"message": command}


@given(parsers.parse('a message with the bio command "{command}"'), target_fixture="context")
def message_with_bio_command_text(command):
    return {"message": command}


@given(parsers.parse('a message with the interests command "{command}"'), target_fixture="context")
def message_with_interests_command_text(command):
    return {"message": command}


@given("a list of messages containing both commands and regular text", target_fixture="messages")
def list_of_messages_with_commands():
    return [
        {"text": "Regular message 1", "author": "john"},
        {"text": "/egregora avatar set https://...", "author": "alice"},
        {"text": "Regular message 2", "author": "bob"},
        {"text": "/egregora bio I am a researcher", "author": "alice"},
        {"text": "Regular message 3", "author": "john"},
    ]


@given("a user command message for an avatar update", target_fixture="command_message")
def user_avatar_command_message():
    return {
        "text": "/egregora avatar set https://example.com/avatar.jpg",
        "author_uuid": "john-uuid",
        "author_name": "John Doe",
        "timestamp": "2025-03-07T10:00:00",
    }


@given("a user command message for a bio update", target_fixture="command_message")
def user_bio_command_message():
    return {
        "text": "/egregora bio I am an AI researcher",
        "author_uuid": "alice-uuid",
        "author_name": "Alice",
        "timestamp": "2025-03-07T11:00:00",
    }


@given("a user command message for an interests update", target_fixture="command_message")
def user_interests_command_message():
    return {
        "text": "/egregora interests AI, ethics, philosophy",
        "author_uuid": "bob-uuid",
        "author_name": "Bob",
        "timestamp": "2025-03-07T12:00:00",
    }


@given(
    parsers.parse('a message containing an {command_type} update command from "{author_name}"'),
    target_fixture="command_message",
)
def message_with_command(command_type, author_name):
    commands = {
        "avatar": "/egregora avatar set https://example.com/avatar.jpg",
        "bio": "/egregora bio I am a test user",
        "interests": "/egregora interests testing, bdd",
    }
    return {
        "text": commands[command_type],
        "author_uuid": f"{author_name.lower().replace(' ', '-')}-uuid",
        "author_name": author_name,
        "timestamp": "2025-03-07T10:00:00",
    }


@given(
    "a message containing a bio update command",
    target_fixture="command_message",
)
def message_with_bio_command():
    return {
        "text": "/egregora bio I am an AI researcher",
        "author_uuid": "alice-uuid",
        "author_name": "Alice",
        "timestamp": "2025-03-07T11:00:00",
    }


@given(
    "a message containing an interests update command",
    target_fixture="command_message",
)
def message_with_interests_command():
    return {
        "text": "/egregora interests AI, ethics, philosophy",
        "author_uuid": "bob-uuid",
        "author_name": "Bob",
        "timestamp": "2025-03-07T12:00:00",
    }


# When Steps


@when(parsers.parse('I parse the message "{message}"'), target_fixture="context")
def parse_the_message(context, message):
    context["is_command"] = is_command(message)
    if context["is_command"]:
        context["parsed_command"] = parse_command(message)
    return context


@when(
    parsers.parse('I check if the message "{message}" is a command'),
    target_fixture="context",
)
def check_if_message_is_command(context, message):
    context["is_command"] = is_command(message)
    return context


@when("the system checks if it is a command", target_fixture="context")
def system_checks_if_command(context):
    return check_if_message_is_command(context, context["message"])


@when("the system parses the command", target_fixture="context")
def system_parses_command(context):
    return parse_the_message(context, context["message"])


@when(
    "I filter the command messages from the list",
    target_fixture="context",
)
def filter_the_messages(context, messages):
    context["filtered_messages"] = filter_commands(messages)
    return context


@when("the system filters out the command messages", target_fixture="context")
def system_filters_command_messages(context, messages):
    return filter_the_messages(context, messages)


@when(
    "I extract the command messages from the list",
    target_fixture="context",
)
def extract_the_commands(context, messages):
    context["extracted_commands"] = extract_commands(messages)
    return context


@when("the system extracts the command messages", target_fixture="context")
def system_extracts_command_messages(context, messages):
    return extract_the_commands(context, messages)


@when(
    "an announcement is created from the message",
    target_fixture="context",
)
def create_announcement_from_message(context, command_message):
    context["announcement"] = command_to_announcement(command_message)
    return context


@when("the system generates an announcement from the command", target_fixture="context")
def system_generates_announcement(context, command_message):
    return create_announcement_from_message(context, command_message)


# Then Steps


@then("the message should be identified as a command")
def message_is_command(context):
    assert context["is_command"]


@then("it should be identified as a command")
def message_is_command_alias(context):
    return message_is_command(context)


@then("it should not be identified as a command")
def message_is_not_command(context):
    assert not context["is_command"]


@then(parsers.parse('the command type should be "{cmd_type}"'))
def command_type_matches(context, cmd_type):
    assert context["parsed_command"]["type"] == cmd_type


@then(parsers.parse('the action should be "{action}"'))
def command_action_matches(context, action):
    assert context["parsed_command"]["action"] == action


@then(parsers.parse('the URL parameter should contain "{url}"'))
def command_url_contains(context, url):
    assert url in context["parsed_command"]["params"]["url"]


@then(parsers.parse('the bio parameter should contain "{bio}"'))
def command_bio_contains(context, bio):
    assert bio in context["parsed_command"]["params"]["bio"]


@then(parsers.parse('the interests parameter should contain "{interests}"'))
def command_interests_contains(context, interests):
    assert interests in context["parsed_command"]["params"]["interests"]


@then(parsers.parse('the parsed command should have type "{cmd_type}" and action "{cmd_action}"'))
def parsed_command_has_type_action(context, cmd_type, cmd_action):
    assert context["parsed_command"]["type"] == cmd_type
    assert context["parsed_command"]["action"] == cmd_action


@then(parsers.parse('the parsed command parameters should contain the url "{url}"'))
def parsed_command_has_url(context, url):
    assert url in context["parsed_command"]["params"]["url"]


@then(parsers.parse('the parsed command parameters should contain the bio "{bio}"'))
def parsed_command_has_bio(context, bio):
    assert bio in context["parsed_command"]["params"]["bio"]


@then(parsers.parse('the parsed command parameters should contain the interests "{interests}"'))
def parsed_command_has_interests(context, interests):
    assert interests in context["parsed_command"]["params"]["interests"]


@then("the resulting list should contain only non-command messages")
def list_has_no_commands(context):
    assert len(context["filtered_messages"]) == 3
    assert all("/egregora" not in m["text"].lower() for m in context["filtered_messages"])


@then("the resulting list should contain only command messages")
def list_has_only_commands(context):
    assert len(context["extracted_commands"]) == 2
    assert all("/egregora" in m["text"].lower() for m in context["extracted_commands"])


@then("the resulting list should only contain regular messages")
def list_only_regular_messages(context):
    return list_has_no_commands(context)


@then("the resulting list should only contain command messages")
def list_only_command_messages(context):
    return list_has_only_commands(context)


@then(parsers.parse('a document of type "{doc_type}" should be generated'))
def document_has_type(context, doc_type):
    assert context["announcement"].type == DocumentType[doc_type]


@then(parsers.parse('its event type should be "{event_type}"'))
def announcement_has_event_type(context, event_type):
    assert context["announcement"].metadata["event_type"] == event_type


@then(parsers.parse('the actor should be "{author_name}"'))
def announcement_has_actor(context, author_name):
    uuid = f"{author_name.lower().replace(' ', '-')}-uuid"
    assert context["announcement"].metadata["actor"] == uuid


@then('the document should be authored by "Egregora"')
def document_authored_by_egregora(context):
    authors = context["announcement"].metadata["authors"]
    assert len(authors) == 1
    assert authors[0]["uuid"] == EGREGORA_UUID
    assert authors[0]["name"] == EGREGORA_NAME


@then("an ANNOUNCEMENT document should be created")
def announcement_document_created(context):
    assert context["announcement"].type == DocumentType.ANNOUNCEMENT


@then(parsers.parse('the document\'s event type should be "{event_type}"'))
def document_event_type_matches(context, event_type):
    assert context["announcement"].metadata["event_type"] == event_type


@then("the document should be authored by Egregora")
def document_authored_by_egregora_alias(context):
    return document_authored_by_egregora(context)


@then(parsers.parse('the document\'s actor should be "{actor_uuid}"'))
def document_actor_matches(context, actor_uuid):
    assert context["announcement"].metadata["actor"] == actor_uuid


@then("the document's content should mention the user and the avatar update")
def document_content_mentions_avatar_update(context):
    assert "John Doe" in context["announcement"].content
    assert "avatar" in context["announcement"].content.lower()


@then("the document's content should contain the new bio text")
def document_content_contains_bio(context):
    assert "I am an AI researcher" in context["announcement"].content


@then("the document's content should contain the new interests")
def document_content_contains_interests(context):
    assert "AI, ethics, philosophy" in context["announcement"].content
