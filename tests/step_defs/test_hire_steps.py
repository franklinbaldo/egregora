from unittest.mock import patch

import pytest
from jules.cli.my_tools import app
from jules.features.hire import HireManager
from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner

scenarios("../features/hire.feature")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_fs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@given("the Jules environment is initialized")
def init_env(isolated_fs):
    dot_jules = isolated_fs / ".jules"
    dot_jules.mkdir(parents=True, exist_ok=True)
    (dot_jules / "personas").mkdir(parents=True, exist_ok=True)


@given(parsers.parse('a persona directory "{path}" exists'))
def persona_exists(isolated_fs, path):
    (isolated_fs / path).mkdir(parents=True, exist_ok=True)


@given(parsers.parse('a logged in persona "{p_id}"'))
def mock_login(p_id):
    # Mocking session manager globally in when steps
    pass


@when(
    parsers.re(
        r'I hire a new persona with id "(?P<id>[^"]+)", name "(?P<name>[^"]+)", emoji "(?P<emoji>[^"]+)", role "(?P<role>[^"]+)", description "(?P<description>[^"]+)", and mission "(?P<mission>[^"]+)"'
    ),
    target_fixture="result",
)
def hire_persona(runner, isolated_fs, persona_id, name, emoji, role, description, mission):
    args = [
        "hire",
        "--id",
        persona_id,
        "--emoji",
        emoji,
        "--description",
        description,
        "--role",
        role,
        "--goal",
        mission,
        "--password",
        "any",
    ]

    with patch("jules.cli.my_tools.session_manager") as mock_session:
        mock_session.get_active_persona.return_value = "artisan"
        mock_session.validate_password.return_value = True

        with patch("jules.cli.my_tools.hire_manager") as mock_hire_mgr:
            # We want to use a real HireManager but pointed to our isolated FS
            real_hire_mgr = HireManager(personas_root=isolated_fs / ".jules" / "personas")
            mock_hire_mgr.hire_persona.side_effect = real_hire_mgr.hire_persona

            return runner.invoke(app, args)


@then(parsers.parse('a new persona directory "{path}" should exist'))
def verify_dir(isolated_fs, path):
    assert (isolated_fs / path).is_dir()


@then(parsers.parse('the prompt file "{path}" should match the RGCCOV pattern'))
def verify_prompt_pattern(isolated_fs, path):
    prompt_path = isolated_fs / path
    assert prompt_path.exists()
    content = prompt_path.read_text()
    assert '{% extends "base/persona.md.j2" %}' in content
    assert "{% block role %}" in content
    assert "{% block goal %}" in content
    assert "{% block workflow %}" in content
    assert "hired_by:" in content


@then(parsers.parse('the prompt frontmatter for "{p_id}" should have "hired_by" set to "{hirer}"'))
def verify_hirer_metadata(isolated_fs, p_id, hirer):
    import frontmatter

    prompt_path = isolated_fs / ".jules" / "personas" / p_id / "prompt.md.j2"
    post = frontmatter.load(prompt_path)
    assert post.metadata.get("hired_by") == hirer


@then(parsers.parse('the persona "{p_id}" should appear in "my-tools roster list"'))
def verify_roster(runner, isolated_fs, p_id):
    # Roster list uses get_personas_dir()
    with patch("jules.cli.roster.get_personas_dir") as mock_get_dir:
        mock_get_dir.return_value = isolated_fs / ".jules" / "personas"
        result = runner.invoke(app, ["roster", "list"])
        assert p_id in result.stdout


@then(parsers.parse('the hire command should fail with "{message}"'))
def verify_failure(result, message):
    assert result.exit_code != 0
    assert message in result.stdout
