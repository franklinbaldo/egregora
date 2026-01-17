import csv
import json
from unittest.mock import patch

import pytest
from jules.cli.my_tools import app
from jules.features.voting import VoteManager
from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner

scenarios("../features/voting.feature")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_fs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Re-instantiate VoteManager to use the isolated path
    return tmp_path


@given("the Jules environment is initialized")
def init_env(isolated_fs):
    dot_jules = isolated_fs / ".jules"
    dot_jules.mkdir(parents=True, exist_ok=True)


@given(parsers.parse('a schedule exists in "{path}"'))
def create_schedule(isolated_fs, path):
    schedule_file = isolated_fs / path
    schedule_file.parent.mkdir(parents=True, exist_ok=True)
    with open(schedule_file, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"]
        )
        writer.writeheader()
        writer.writerow(
            {"sequence": "001", "persona": "absolutist", "session_id": "123", "pr_status": "merged"}
        )
        writer.writerow({"sequence": "020", "persona": "artisan"})
        writer.writerow({"sequence": "025", "persona": "typeguard"})


@given(parsers.parse('a logged in persona "{p_id}" with password "{password}"'))
def mock_login(p_id, password):
    # This will be handled by patching SessionManager in the 'when' step
    pass


@given(parsers.parse('a logged in persona "{p_id}"'))
def mock_login_simple(p_id):
    pass


@given(parsers.parse('sequence "{seq_id}" has already been executed'))
def mark_executed(isolated_fs, seq_id):
    # Already handled in create_schedule for 001
    pass


@given(parsers.parse('sequence "{seq_id}" currently has "{persona}" in the schedule'))
def verify_initial_state(isolated_fs, seq_id, persona):
    # Verification of initial state if needed
    pass


@given(parsers.parse('"{voter}" voted for "{target}" for sequence "{seq_id}"'))
def manual_vote(isolated_fs, voter, target, seq_id):
    vote_mgr = VoteManager(schedule_file=isolated_fs / ".jules" / "schedule.csv")
    vote_mgr.votes_root = isolated_fs / ".jules" / "votes"
    vote_mgr.cast_vote(seq_id, voter, target)


@when(
    parsers.parse('I vote for persona "{persona}" to occupy sequence "{sequence}"'), target_fixture="result"
)
def cast_vote(runner, isolated_fs, persona, sequence):
    with patch("jules.cli.my_tools.session_manager") as mock_session:
        # Mock active persona and password validation
        mock_session.get_active_persona.return_value = "artisan"
        mock_session.validate_password.return_value = True

        # Inject isolated paths into the live vote_manager
        with patch("jules.cli.my_tools.vote_manager") as mock_vote_mgr:
            real_vote_mgr = VoteManager(schedule_file=isolated_fs / ".jules" / "schedule.csv")
            real_vote_mgr.votes_root = isolated_fs / ".jules" / "votes"
            mock_vote_mgr.cast_vote.side_effect = real_vote_mgr.cast_vote

            return runner.invoke(
                app,
                [
                    "vote",
                    "--sequence",
                    sequence,
                    "--persona",
                    persona,
                    "--password",
                    "c28d7168-5435-512c-9154-8c887413a697",
                ],
            )


@when(
    parsers.parse('I attempt to vote for persona "{persona}" to occupy sequence "{sequence}"'),
    target_fixture="result",
)
def attempt_invalid_vote(runner, isolated_fs, persona, sequence):
    with patch("jules.cli.my_tools.session_manager") as mock_session:
        mock_session.get_active_persona.return_value = "curator"
        mock_session.validate_password.return_value = True

        with patch("jules.cli.my_tools.vote_manager") as mock_vote_mgr:
            real_vote_mgr = VoteManager(schedule_file=isolated_fs / ".jules" / "schedule.csv")
            real_vote_mgr.votes_root = isolated_fs / ".jules" / "votes"
            mock_vote_mgr.cast_vote.side_effect = real_vote_mgr.cast_vote

            return runner.invoke(
                app, ["vote", "--sequence", sequence, "--persona", persona, "--password", "any"]
            )


@when("the voting results are applied")
def apply_results(isolated_fs):
    vote_mgr = VoteManager(schedule_file=isolated_fs / ".jules" / "schedule.csv")
    vote_mgr.votes_root = isolated_fs / ".jules" / "votes"
    vote_mgr.apply_votes("025")


@then(parsers.parse('a vote record should be created in ".jules/votes/{sequence}/{voter}.json"'))
def verify_vote_file(isolated_fs, sequence, voter):
    vote_file = isolated_fs / ".jules" / "votes" / sequence / f"{voter}.json"
    assert vote_file.exists()


@then(parsers.parse('the vote should count for "{persona}"'))
def verify_vote_content(isolated_fs, persona):
    # We'll just check one of the vote files created
    vote_files = list((isolated_fs / ".jules" / "votes").glob("**/*.json"))
    assert len(vote_files) > 0
    data = json.loads(vote_files[0].read_text())
    assert data["persona"] == persona


@then("the system should reject the vote with an error")
def verify_error(result):
    assert result.exit_code != 0
    assert "Vote failed" in result.stdout


@then(parsers.parse('sequence "{seq_id}" in "schedule.csv" should be changed to "{persona}"'))
def verify_schedule_update(isolated_fs, seq_id, persona):
    schedule_file = isolated_fs / ".jules" / "schedule.csv"
    with open(schedule_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["sequence"] == seq_id:
                assert row["persona"] == persona
                return
    pytest.fail(f"Sequence {seq_id} not found in schedule.csv")
