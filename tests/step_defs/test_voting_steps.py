import csv
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
    return tmp_path


@given("the Jules environment is initialized")
def init_env(isolated_fs):
    dot_jules = isolated_fs / ".jules"
    dot_jules.mkdir(parents=True, exist_ok=True)
    personas_dir = dot_jules / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    for i in range(27):
        (personas_dir / f"persona_{i}").mkdir(parents=True, exist_ok=True)


@given(parsers.parse('a schedule exists where "{p_id}" is at sequence "{seq_id}"'))
def create_targeted_schedule(isolated_fs, p_id, seq_id):
    schedule_file = isolated_fs / ".jules" / "schedule.csv"
    schedule_file.parent.mkdir(parents=True, exist_ok=True)
    with schedule_file.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"]
        )
        writer.writeheader()
        writer.writerow({"sequence": seq_id, "persona": p_id, "session_id": "active_sess"})
        target_seq = f"{int(seq_id) + 28:03}"
        writer.writerow({"sequence": target_seq, "persona": "placeholder"})


@given(parsers.parse('a logged in persona "{p_id}" with password "{password}"'))
def mock_login_with_pass(p_id, password):
    pass


@given(parsers.parse('a schedule exists in "{path}"'))
def create_schedule(isolated_fs, path):
    schedule_file = isolated_fs / path
    schedule_file.parent.mkdir(parents=True, exist_ok=True)
    with schedule_file.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"]
        )
        writer.writeheader()
        writer.writerow(
            {"sequence": "001", "persona": "absolutist", "session_id": "123", "pr_status": "merged"}
        )


@when(parsers.parse('I vote for personas "{p1}" and "{p2}"'), target_fixture="result")
def cast_ranked_votes(runner, isolated_fs, p1, p2):
    with patch("jules.cli.my_tools.session_manager") as mock_session:
        mock_session.get_active_persona.return_value = "artisan"
        mock_session.validate_password.return_value = True
        with patch("jules.cli.my_tools.vote_manager") as mock_vote_mgr:
            real_vote_mgr = VoteManager(
                schedule_file=isolated_fs / ".jules" / "schedule.csv",
                votes_file=isolated_fs / ".jules" / "votes.csv",
            )
            with patch("jules.features.voting.PERSONAS_ROOT", isolated_fs / ".jules" / "personas"):
                mock_vote_mgr.cast_vote.side_effect = real_vote_mgr.cast_vote
                mock_vote_mgr.get_current_sequence.side_effect = real_vote_mgr.get_current_sequence
                return runner.invoke(app, ["vote", "-p", p1, "-p", p2, "--password", "any"])


@then(parsers.parse('a vote record should be created in ".jules/votes.csv"'))
def verify_vote_csv(isolated_fs):
    assert (isolated_fs / ".jules" / "votes.csv").exists()


@then(parsers.parse('the CSV should contain a "rank {rank}" vote for "{persona}" from "{voter_seq}"'))
def verify_ranked_vote(isolated_fs, rank, persona, voter_seq):
    found = False
    with (isolated_fs / ".jules" / "votes.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (
                row["voter_sequence"] == voter_seq
                and row["candidate_persona_choosed"] == persona
                and row["rank"] == str(rank)
            ):
                found = True
                break
    assert found, f"Rank {rank} vote for {persona} from {voter_seq} not found."


@given(parsers.parse('sequence "{seq_id}" currently has "{persona}" in the schedule'))
def verify_initial_state(isolated_fs, seq_id, persona):
    schedule_file = isolated_fs / ".jules" / "schedule.csv"
    rows = []
    found = False
    if schedule_file.exists():
        with schedule_file.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["sequence"] == seq_id:
                    row["persona"] = persona
                    found = True
                rows.append(row)
    if not found:
        rows.append({"sequence": seq_id, "persona": persona})
    with schedule_file.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"]
        )
        writer.writeheader()
        writer.writerows(rows)


@given(
    parsers.re(
        r'sequence "(?P<voter_seq>\d+)" ranked "(?P<p1>\w+)" as #(?P<r1>\d+) and "(?P<p2>\w+)" as #(?P<r2>\d+) for "(?P<seq_id>\d+)"'
    )
)
def manual_ranked_votes(isolated_fs, voter_seq, p1, r1, p2, r2, seq_id):
    votes_file = isolated_fs / ".jules" / "votes.csv"
    file_exists = votes_file.exists()
    with votes_file.open("a", newline="") as f:
        fieldnames = ["voter_sequence", "sequence_cast", "candidate_persona_choosed", "rank"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "voter_sequence": voter_seq,
                "sequence_cast": seq_id,
                "candidate_persona_choosed": p1,
                "rank": r1.replace("#", ""),
            }
        )
        writer.writerow(
            {
                "voter_sequence": voter_seq,
                "sequence_cast": seq_id,
                "candidate_persona_choosed": p2,
                "rank": r2.replace("#", ""),
            }
        )


@given(
    parsers.re(r'sequence "(?P<voter_seq>\d+)" ranked "(?P<p1>\w+)" as #(?P<r1>\d+) for "(?P<seq_id>\d+)"')
)
def manual_single_ranked_vote(isolated_fs, voter_seq, p1, r1, seq_id):
    votes_file = isolated_fs / ".jules" / "votes.csv"
    file_exists = votes_file.exists()
    with votes_file.open("a", newline="") as f:
        fieldnames = ["voter_sequence", "sequence_cast", "candidate_persona_choosed", "rank"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "voter_sequence": voter_seq,
                "sequence_cast": seq_id,
                "candidate_persona_choosed": p1,
                "rank": r1.replace("#", ""),
            }
        )


@when(parsers.parse('the voting results are applied to sequence "{seq_id}"'))
def apply_results_to_seq(isolated_fs, seq_id):
    vote_mgr = VoteManager(
        schedule_file=isolated_fs / ".jules" / "schedule.csv", votes_file=isolated_fs / ".jules" / "votes.csv"
    )
    with patch("jules.features.voting.PERSONAS_ROOT", isolated_fs / ".jules" / "personas"):
        vote_mgr.apply_votes(seq_id)


@then(parsers.parse('sequence "{seq_id}" in "schedule.csv" should be changed to "{persona}"'))
def verify_schedule_update(isolated_fs, seq_id, persona):
    schedule_file = isolated_fs / ".jules" / "schedule.csv"
    with schedule_file.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["sequence"] == seq_id:
                assert row["persona"] == persona
                return
    pytest.fail(f"Sequence {seq_id} not found in schedule.csv")
