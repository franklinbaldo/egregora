from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from egregora.agents.avatar import AvatarContext, AvatarProcessingError, process_avatar_commands

# Load scenarios
scenarios("../features/avatar_command_processing.feature")


@pytest.fixture
def avatar_context():
    return AvatarContext(
        docs_dir=Path("/docs"),
        media_dir=Path("/media"),
        profiles_dir=Path("/profiles"),
        vision_model="mock_model",
    )


@pytest.fixture
def mock_dependencies():
    with (
        patch("egregora.agents.avatar.extract_commands") as mock_extract,
        patch("egregora.agents.avatar._create_secure_client") as mock_client_creator,
        patch("egregora.agents.avatar.download_avatar_from_url") as mock_download,
        patch("egregora.agents.avatar.update_profile_avatar") as mock_update,
        patch("egregora.agents.avatar.remove_profile_avatar") as mock_remove,
        patch("egregora.agents.avatar.enrich_avatar") as mock_enrich,
    ):
        # Setup mock client
        mock_client = MagicMock()
        mock_client_creator.return_value.__enter__.return_value = mock_client

        yield {
            "extract": mock_extract,
            "create_client": mock_client_creator,
            "client": mock_client,
            "download": mock_download,
            "update": mock_update,
            "remove": mock_remove,
            "enrich": mock_enrich,
        }


@pytest.fixture
def command_list():
    return []


# Given steps


@given("a configured AvatarContext")
def setup_context(avatar_context):
    pass  # Fixture does the work


@given(parsers.parse('a user "{author}" has issued a command to set avatar to "{url}"'))
def add_set_command(command_list, author, url):
    command_list.append(
        {
            "command": {"command": "set", "target": "avatar", "value": url},
            "author": author,
            "timestamp": "2023-01-01T12:00:00",
        }
    )


@given(parsers.parse('a user "{author}" has issued a command to unset avatar'))
def add_unset_command(command_list, author):
    command_list.append(
        {
            "command": {"command": "unset", "target": "avatar"},
            "author": author,
            "timestamp": "2023-01-01T12:00:00",
        }
    )


@given(parsers.parse('a user "{author}" has issued a command to set "{target}" to "{value}"'))
def add_other_command(command_list, author, target, value):
    command_list.append(
        {
            "command": {"command": "set", "target": target, "value": value},
            "author": author,
            "timestamp": "2023-01-01T12:00:00",
        }
    )


@given(parsers.parse('the download for "{url}" will fail with an error'))
def setup_download_failure(mock_dependencies, url):
    # We need to preserve existing side effects if any, or create a new wrapper
    # The default return value is set in the process_commands step if no side effect exists.
    # But here we want to override specifically for this URL.

    def side_effect(download_url, *args, **kwargs):
        if download_url == url:
            msg = f"Simulated download failure for {url}"
            raise AvatarProcessingError(msg)

        # If there was a previous side effect, delegate to it (unless it's this one recursively, but we are creating a new closure)
        # However, to keep it simple: if not failing, return success
        return ("mock_uuid", Path("/mock/path"))

    mock_dependencies["download"].side_effect = side_effect


# When steps


@when("the system processes the avatar commands", target_fixture="results")
def process_commands(avatar_context, command_list, mock_dependencies):
    mock_dependencies["extract"].return_value = command_list

    # Setup default return value if no side effect is set
    if mock_dependencies["download"].side_effect is None:
        mock_dependencies["download"].return_value = ("mock_uuid", Path("/mock/path"))

    return process_avatar_commands(MagicMock(), avatar_context)


# Then steps


@then(parsers.parse('the avatar should be downloaded from "{url}"'))
def verify_download(mock_dependencies, url):
    calls = mock_dependencies["download"].call_args_list
    urls_downloaded = [call.kwargs.get("url") or call.args[0] for call in calls]
    assert url in urls_downloaded


@then(parsers.parse('the profile for "{author}" should be updated with the new avatar'))
def verify_profile_update(mock_dependencies, author):
    calls = mock_dependencies["update"].call_args_list
    authors_updated = [call.kwargs.get("author_uuid") for call in calls]
    assert author in authors_updated


@then(parsers.parse('the command result for "{author}" should indicate success'))
def verify_success_result(results, author):
    assert author in results
    assert "✅" in results[author]


@then("the HTTP client should be created exactly once")
def verify_client_creation_once(mock_dependencies):
    mock_dependencies["create_client"].assert_called_once()


@then(parsers.parse('the avatar for "{author}" should be processed using the client'))
def verify_client_usage(mock_dependencies, author):
    mock_client = mock_dependencies["client"]
    calls = mock_dependencies["download"].call_args_list

    # Verify that at least one call used the client (we can't easily filter by author without tracking URLs)
    # But since we know the logic passes the client to all calls in the loop...
    client_usage = [call.kwargs.get("client") == mock_client for call in calls]
    assert any(client_usage)


@then(parsers.parse('the profile for "{author}" should have its avatar removed'))
def verify_avatar_removed(mock_dependencies, author):
    calls = mock_dependencies["remove"].call_args_list
    authors_removed = [call.kwargs.get("author_uuid") for call in calls]
    assert author in authors_removed


@then(parsers.parse('the command result for "{author}" should indicate failure'))
def verify_failure_result(results, author):
    assert author in results
    assert "❌" in results[author]


@then(parsers.parse('the profile for "{author}" should NOT be updated'))
def verify_profile_not_updated(mock_dependencies, author):
    calls = mock_dependencies["update"].call_args_list
    authors_updated = [call.kwargs.get("author_uuid") for call in calls]
    assert author not in authors_updated


@then(parsers.parse('no avatar processing should occur for "{author}"'))
def verify_no_processing(mock_dependencies, author):
    update_calls = mock_dependencies["update"].call_args_list
    remove_calls = mock_dependencies["remove"].call_args_list

    authors_updated = [call.kwargs.get("author_uuid") for call in update_calls]
    authors_removed = [call.kwargs.get("author_uuid") for call in remove_calls]

    assert author not in authors_updated
    assert author not in authors_removed
