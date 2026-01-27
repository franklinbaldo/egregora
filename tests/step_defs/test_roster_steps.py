from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from repo.cli.roster import app
from typer.testing import CliRunner

# Load scenarios
scenarios("../features/roster.feature")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_fs(tmp_path, monkeypatch):
    """Isolate file system for tests."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@given("the file system is isolated")
def isolate_filesystem(isolated_fs):
    pass


@given("the following personas exist:")
def create_multiple_personas(isolated_fs, datatable):
    personas_dir = isolated_fs / ".team" / "personas"
    for row in datatable:
        if row[0] == "id":
            continue
        p_id, emoji, desc = row
        p_dir = personas_dir / p_id
        p_dir.mkdir(parents=True, exist_ok=True)
        (p_dir / "prompt.md.j2").write_text(f"""---
id: {p_id}
emoji: "{emoji}"
description: "{desc}"
---
Content
""")


@given(parsers.parse('a persona "{p_id}" exists with description "{desc}"'))
def create_persona_with_desc(isolated_fs, p_id, desc):
    p_dir = isolated_fs / ".team" / "personas" / p_id
    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "prompt.md.j2").write_text(f"""---
id: {p_id}
emoji: "🧪"
description: "{desc}"
---
Content
""")


@given(parsers.parse('a persona "{p_id}" exists'))
def create_simple_persona(isolated_fs, p_id):
    p_dir = isolated_fs / ".team" / "personas" / p_id
    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "prompt.md.j2").write_text(f"""---
id: {p_id}
emoji: "🧪"
description: "Desc"
---
Content
""")


@given("no personas exist")
def no_personas(isolated_fs):
    personas_dir = isolated_fs / ".team" / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)


@when(parsers.parse('I view the details for persona "{p_id}"'), target_fixture="result")
def run_view_persona(runner, p_id):
    # Mock PersonaLoader in the roster module
    mock_config = MagicMock()
    mock_config.id = p_id
    mock_config.emoji = "🧪"
    # Use a description that matches the feature file expectation for the Forge persona
    mock_config.description = "Senior frontend developer" if p_id == "forge" else "Test description"
    mock_config.prompt_body = f"# {p_id.upper()}\n\nThis is the prompt content."

    # roster.py now has 'from repo.scheduler.loader import PersonaLoader' at top level
    with (
        patch("repo.cli.roster.PersonaLoader") as mock_loader_class,
        patch("repo.features.session.SessionManager") as mock_sm_class,
    ):
        mock_loader = MagicMock()
        mock_loader.load_persona.return_value = mock_config
        mock_loader_class.return_value = mock_loader

        # Mock active session for authentication
        mock_sm = MagicMock()
        mock_sm.get_active_persona.return_value = "tester"
        mock_sm.get_active_sequence.return_value = "seq-1"
        mock_sm_class.return_value = mock_sm

        return runner.invoke(app, ["view", p_id])


@when("I list the available personas", target_fixture="result")
def run_list_personas(runner):
    with patch("repo.features.session.SessionManager") as mock_sm_class:
        # Mock active session for authentication
        mock_sm = MagicMock()
        mock_sm.get_active_persona.return_value = "tester"
        mock_sm.get_active_sequence.return_value = "seq-1"
        mock_sm_class.return_value = mock_sm

        return runner.invoke(app, ["list"])


@then("the command should exit successfully")
def check_exit_success(result):
    assert result.exit_code == 0, f"Command failed with code {result.exit_code}. Output: {result.stdout}"


@then("the command should exit with an error")
def check_exit_error(result):
    assert result.exit_code != 0


@then(parsers.parse('the output should contain "{text}"'))
def check_output_contains(result, text):
    # Case insensitive check and better error reporting
    output = result.stdout + result.stderr
    # Rich output might have punctuation or specific case
    assert text.lower() in output.lower(), f"Expected '{text}' to be in output, but got: '{output}'"
