import pytest
import csv
import json
from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner
from pathlib import Path
from unittest.mock import patch, MagicMock
from jules.cli.my_tools import app
from jules.features.voting import VoteManager

scenarios("../features/voting.feature")

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
    # Create 27 dummy personas for roster size calculation
    personas_dir = dot_jules / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    for i in range(27):
        (personas_dir / f"persona_{i}").mkdir(parents=True, exist_ok=True)

@given(parsers.parse('a schedule exists in "{path}"'))
def create_schedule(isolated_fs, path):
    schedule_file = isolated_fs / path
    schedule_file.parent.mkdir(parents=True, exist_ok=True)
    with open(schedule_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"])
        writer.writeheader()
        writer.writerow({"sequence": "001", "persona": "absolutist", "session_id": "123", "pr_status": "merged"})
        writer.writerow({"sequence": "020", "persona": "artisan"})
        writer.writerow({"sequence": "025", "persona": "typeguard"})

@given(parsers.parse('a schedule exists where "{p_id}" is at sequence "{seq_id}"'))
def create_targeted_schedule(isolated_fs, p_id, seq_id):
    schedule_file = isolated_fs / ".jules" / "schedule.csv"
    schedule_file.parent.mkdir(parents=True, exist_ok=True)
    with open(schedule_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"])
        writer.writeheader()
        # Ensure we have the sequence requested
        writer.writerow({"sequence": seq_id, "persona": p_id, "session_id": "active_sess"})
        # Target sequence for testing (seq_id + 27 + 1 = seq_id + 28)
        target_seq = f"{int(seq_id) + 28:03}"
        writer.writerow({"sequence": target_seq, "persona": "placeholder"})

@given(parsers.parse('a logged in persona "{p_id}" with password "{password}"'))
def mock_login_with_pass(p_id, password):
    pass

@given(parsers.parse('a logged in persona "{p_id}"'))
def mock_login_simple(p_id):
    pass

@given(parsers.parse('sequence "{seq_id}" currently has "{persona}" in the schedule'))
def verify_initial_state(isolated_fs, seq_id, persona):
    schedule_file = isolated_fs / ".jules" / "schedule.csv"
    if not schedule_file.exists():
        with open(schedule_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"])
            writer.writeheader()
    
    # Read existing rows
    rows = []
    found = False
    with open(schedule_file, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['sequence'] == seq_id:
                row['persona'] = persona
                found = True
            rows.append(row)
    
    if not found:
        rows.append({"sequence": seq_id, "persona": persona})
        
    with open(schedule_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"])
        writer.writeheader()
        writer.writerows(rows)

@given(parsers.parse('sequence "{voter_seq}" voted for "{target}" for sequence "{seq_id}"'))
def manual_vote(isolated_fs, voter_seq, target, seq_id):
    votes_file = isolated_fs / ".jules" / "votes.csv"
    file_exists = votes_file.exists()
    with open(votes_file, mode='a', newline='') as f:
        fieldnames = ['voter_sequence', 'sequence_cast', 'candidate_persona_choosed']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            'voter_sequence': voter_seq,
            'sequence_cast': seq_id,
            'candidate_persona_choosed': target
        })

@when(parsers.parse('I vote for persona "{persona}"'), target_fixture="result")
def cast_vote(runner, isolated_fs, persona):
    with patch("jules.cli.my_tools.session_manager") as mock_session:
        # We need to mock get_active_persona and validate_password
        # In the scenario where password is provided, we just return True
        mock_session.get_active_persona.return_value = "artisan"
        mock_session.validate_password.return_value = True
        
        with patch("jules.cli.my_tools.vote_manager") as mock_vote_mgr:
            real_vote_mgr = VoteManager(
                schedule_file=isolated_fs / ".jules" / "schedule.csv",
                votes_file=isolated_fs / ".jules" / "votes.csv"
            )
            # Patch personas_root in the REAL manager
            with patch("jules.features.voting.PERSONAS_ROOT", isolated_fs / ".jules" / "personas"):
                mock_vote_mgr.cast_vote.side_effect = real_vote_mgr.cast_vote
                mock_vote_mgr.get_current_sequence.side_effect = real_vote_mgr.get_current_sequence
                return runner.invoke(app, ["vote", "--persona", persona, "--password", "any"])

@when(parsers.parse('the voting results are applied to sequence "{seq_id}"'))
def apply_results_to_seq(isolated_fs, seq_id):
    vote_mgr = VoteManager(
        schedule_file=isolated_fs / ".jules" / "schedule.csv",
        votes_file=isolated_fs / ".jules" / "votes.csv"
    )
    vote_mgr.apply_votes(seq_id)

@then(parsers.parse('a vote record should be created in ".jules/votes.csv"'))
def verify_vote_csv(isolated_fs):
    assert (isolated_fs / ".jules" / "votes.csv").exists()

@then(parsers.parse('the vote should have voter "{voter_seq}" and target sequence "{target_seq}"'))
def verify_vote_details(isolated_fs, voter_seq, target_seq):
    with open(isolated_fs / ".jules" / "votes.csv", mode='r', newline='') as f:
        reader = csv.DictReader(f)
        last_row = list(reader)[-1]
        assert last_row['voter_sequence'] == voter_seq
        assert last_row['sequence_cast'] == target_seq

@then(parsers.parse('the vote should count for "{persona}"'))
def verify_vote_content(isolated_fs, persona):
    with open(isolated_fs / ".jules" / "votes.csv", mode='r', newline='') as f:
        reader = csv.DictReader(f)
        last_row = list(reader)[-1]
        assert last_row['candidate_persona_choosed'] == persona

@then(parsers.parse('sequence "{seq_id}" in "schedule.csv" should be changed to "{persona}"'))
def verify_schedule_update(isolated_fs, seq_id, persona):
    schedule_file = isolated_fs / ".jules" / "schedule.csv"
    with open(schedule_file, mode='r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['sequence'] == seq_id:
                assert row['persona'] == persona
                return
    pytest.fail(f"Sequence {seq_id} not found in schedule.csv")
