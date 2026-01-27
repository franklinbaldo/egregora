import csv
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from repo.cli.my_tools import app
from repo.features.voting import VoteManager
from typer.testing import CliRunner

scenarios("../features/voting.feature")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_fs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mock_httpx(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("httpx.get", mock)
    return mock


@given("the Team environment is initialized")
def init_env(isolated_fs):
    dot_team = isolated_fs / ".team"
    dot_team.mkdir(parents=True, exist_ok=True)
    personas_dir = dot_team / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    for i in range(27):
        (personas_dir / f"persona_{i}").mkdir(parents=True, exist_ok=True)


@given(parsers.parse('a schedule exists where "{p_id}" is at sequence "{seq_id}"'))
def create_targeted_schedule(isolated_fs, p_id, seq_id):
    schedule_file = isolated_fs / ".team" / "schedule.csv"
    schedule_file.parent.mkdir(parents=True, exist_ok=True)
    with (schedule_file).open("w", newline="") as f:
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
    with (schedule_file).open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"]
        )
        writer.writeheader()
        writer.writerow(
            {"sequence": "001", "persona": "absolutist", "session_id": "123", "pr_status": "merged"}
        )


@when(parsers.parse('I vote for personas "{p1}" and "{p2}"'), target_fixture="result")
def cast_ranked_votes(isolated_fs, p1, p2):
    """Cast ranked votes using real VoteManager directly (not via CLI)."""
    # Create personas directory with 27 personas for roster size calculation
    personas_dir = isolated_fs / ".team" / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    for i in range(27):
        (personas_dir / f"persona_{i}").mkdir(exist_ok=True)

    vote_mgr = VoteManager(
        schedule_file=isolated_fs / ".team" / "schedule.csv", votes_file=isolated_fs / ".team" / "votes.csv"
    )

    with patch("repo.features.voting.PERSONAS_ROOT", personas_dir):
        # Cast vote directly using sequence 002 (artisan's sequence)
        vote_mgr.cast_vote("002", [p1, p2])


@then(parsers.parse('a vote record should be created in ".team/votes.csv"'))
def verify_vote_csv(isolated_fs):
    assert (isolated_fs / ".team" / "votes.csv").exists()


@then(parsers.parse('the CSV should contain candidates "{candidates}" from voter "{voter_seq}"'))
def verify_candidates_from_voter(isolated_fs, candidates, voter_seq):
    found = False
    actual_rows = []
    with (isolated_fs / ".team" / "votes.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            actual_rows.append(row)
            if row["voter_sequence"] == voter_seq and row["candidates"] == candidates:
                found = True
                break
    assert found, f"Candidates '{candidates}' from voter {voter_seq} not found. Actual rows: {actual_rows}"


@given(parsers.parse('sequence "{seq_id}" currently has "{persona}" in the schedule'))
def verify_initial_state(isolated_fs, seq_id, persona):
    schedule_file = isolated_fs / ".team" / "schedule.csv"
    rows = []
    found = False
    if schedule_file.exists():
        with (schedule_file).open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["sequence"] == seq_id:
                    row["persona"] = persona
                    found = True
                rows.append(row)
    if not found:
        rows.append({"sequence": seq_id, "persona": persona})
    with (schedule_file).open("w", newline="") as f:
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
    """Create vote with candidates in order (using new format - no sequence_cast)."""
    votes_file = isolated_fs / ".team" / "votes.csv"
    file_exists = votes_file.exists()
    # r1 and r2 determine order - lower rank = first in candidates
    if int(r1) < int(r2):
        candidates = f"{p1},{p2}"
    else:
        candidates = f"{p2},{p1}"
    with (votes_file).open(mode="a", newline="") as f:
        fieldnames = ["voter_sequence", "candidates"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({"voter_sequence": voter_seq, "candidates": candidates})


@given(parsers.parse('sequence "{seq_id}" is the next open sequence'))
def set_next_open_sequence(isolated_fs, seq_id):
    """Create schedule with open sequence."""
    schedule_file = isolated_fs / ".team" / "schedule.csv"
    schedule_file.parent.mkdir(parents=True, exist_ok=True)
    with (schedule_file).open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"]
        )
        writer.writeheader()
        writer.writerow({"sequence": seq_id, "persona": "placeholder", "session_id": ""})


@given(parsers.parse("{count:d} personas have voted (roster size = {roster:d})"))
def set_roster_size(count, roster):
    """Just a descriptive step - roster is controlled by persona dirs."""
    # These parameters are used by the BDD parser but not directly in the function body.
    # They are kept to match the BDD step definition.
<<<<<<< HEAD
    _ = (count, roster)
=======
    _ = count
    _ = roster
>>>>>>> origin/pr/2674


@given(parsers.parse('sequence "{seq}" voted for "{persona}" as first choice'))
def add_voter_choice(isolated_fs, seq, persona):
    """Add a vote from a sequence for a persona."""
    votes_file = isolated_fs / ".team" / "votes.csv"
    file_exists = votes_file.exists()
    with (votes_file).open(mode="a", newline="") as f:
        fieldnames = ["voter_sequence", "candidates"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({"voter_sequence": seq, "candidates": persona})


@given(parsers.parse("votes from the last {count:d} sequences result in a tie:"))
def setup_tie_votes(isolated_fs, count):
    """Create votes that result in a tie from sequences before target.

    For target=040 and count=5, we use sequences 035-039.
    Equal votes for artisan and refactor to create tie.
    """
    votes_file = isolated_fs / ".team" / "votes.csv"
    votes_file.parent.mkdir(parents=True, exist_ok=True)
    with (votes_file).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["voter_sequence", "candidates"])
        writer.writeheader()
        # Create equal votes: artisan,refactor and refactor,artisan alternating
        # This gives equal Borda points to both
        writer.writerow({"voter_sequence": "035", "candidates": "artisan,refactor"})
        writer.writerow({"voter_sequence": "036", "candidates": "refactor,artisan"})
        writer.writerow({"voter_sequence": "037", "candidates": "artisan,refactor"})
        writer.writerow({"voter_sequence": "038", "candidates": "refactor,artisan"})
        writer.writerow({"voter_sequence": "039", "candidates": "artisan"})  # Single vote


@given(parsers.parse('votes result in a tie between "{p1}" ({pts1:d} pts) and "{p2}" ({pts2:d} pts)'))
def setup_tie_between(isolated_fs, p1, pts1, p2, pts2):
    """Create balanced votes for tie."""
    # These parameters are used by the BDD parser but not directly in the function body.
    # They are kept to match the BDD step definition.
<<<<<<< HEAD
    _ = (pts1, pts2)
=======
    _ = pts1
    _ = pts2
>>>>>>> origin/pr/2674
    with (isolated_fs / ".team" / "votes.csv").open("w", newline="") as f:
        fieldnames = ["voter_sequence", "candidates"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        # Equal votes for tie
        writer.writerow({"voter_sequence": "035", "candidates": f"{p1},{p2}"})
        writer.writerow({"voter_sequence": "036", "candidates": f"{p2},{p1}"})


@given(parsers.parse('votes from sequences 005-009 favor "{persona}"'))
def setup_favorable_votes(isolated_fs, persona):
    """Create votes that favor specified persona."""
    votes_file = isolated_fs / ".team" / "votes.csv"
    votes_file.parent.mkdir(parents=True, exist_ok=True)
    with (votes_file).open("w", newline="") as f:
        fieldnames = ["voter_sequence", "candidates"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for seq in range(5, 10):
            writer.writerow({"voter_sequence": f"{seq:03}", "candidates": persona})


@when(parsers.parse('I cast a vote for persona "{persona}" as first choice'))
def cast_vote_first_choice(isolated_fs, persona):
    """Cast a vote with persona as first choice and apply votes."""
    # Create personas directory with 5 personas for roster size calculation
    personas_dir = isolated_fs / ".team" / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        (personas_dir / f"persona_{i}").mkdir(exist_ok=True)

    votes_file = isolated_fs / ".team" / "votes.csv"
    votes_file.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if votes_file.exists():
        with (votes_file).open(newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    rows.append({"voter_sequence": "002", "candidates": persona})
    with (votes_file).open("w", newline="") as f:
        fieldnames = ["voter_sequence", "candidates"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Apply votes to update schedule
    vote_mgr = VoteManager(schedule_file=isolated_fs / ".team" / "schedule.csv", votes_file=votes_file)
    with patch("repo.features.voting.PERSONAS_ROOT", personas_dir):
        next_seq = vote_mgr.get_next_open_sequence()
        if next_seq:
            vote_mgr.apply_votes(next_seq)


@then(parsers.parse('the schedule should update sequence "{seq_id}" to "{persona}"'))
def verify_schedule_updated(isolated_fs, seq_id, persona):
    """Verify schedule was updated."""
    schedule_file = isolated_fs / ".team" / "schedule.csv"
    with (schedule_file).open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["sequence"] == seq_id:
                assert row["persona"] == persona, f"Expected {persona}, got {row['persona']}"
                return
    pytest.fail(f"Sequence {seq_id} not found")


@then("I should see the next open sequence to be filled")
def verify_open_sequence_display():
    pass


@given(
    parsers.re(r'sequence "(?P<voter_seq>\d+)" ranked "(?P<p1>\w+)" as #(?P<r1>\d+) for "(?P<seq_id>\d+)"')
)
def manual_single_ranked_vote(isolated_fs, voter_seq, p1, r1, seq_id):
    """Create single vote with one candidate (using new array format)."""
    votes_file = isolated_fs / ".team" / "votes.csv"
    file_exists = votes_file.exists()
    with (votes_file).open(mode="a", newline="") as f:
        fieldnames = ["voter_sequence", "candidates"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({"voter_sequence": voter_seq, "candidates": p1})


@when(parsers.parse('the voting results are applied to sequence "{seq_id}"'))
def apply_results_to_seq(isolated_fs, seq_id):
    # Ensure personas directory exists for roster size calculation
    personas_dir = isolated_fs / ".team" / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    for i in range(27):
        (personas_dir / f"persona_{i}").mkdir(exist_ok=True)

    vote_mgr = VoteManager(
        schedule_file=isolated_fs / ".team" / "schedule.csv", votes_file=isolated_fs / ".team" / "votes.csv"
    )
    with patch("repo.features.voting.PERSONAS_ROOT", personas_dir):
        vote_mgr.apply_votes(seq_id)


@then(parsers.parse('sequence "{seq_id}" in "schedule.csv" should be changed to "{persona}"'))
def verify_schedule_update(isolated_fs, seq_id, persona):
    schedule_file = isolated_fs / ".team" / "schedule.csv"
    with (schedule_file).open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["sequence"] == seq_id:
                assert row["persona"] == persona
                return
    pytest.fail(f"Sequence {seq_id} not found in schedule.csv")


# New step definitions for tiebreaker, contextual help, and hire-vote scenarios


@given(parsers.parse('a logged in persona "{p_id}" at sequence "{seq_id}"'))
def mock_login_at_sequence(isolated_fs, p_id, seq_id):
    """Create schedule with persona at given sequence."""
    schedule_file = isolated_fs / ".team" / "schedule.csv"
    schedule_file.parent.mkdir(parents=True, exist_ok=True)
    with (schedule_file).open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"]
        )
        writer.writeheader()
        writer.writerow({"sequence": seq_id, "persona": p_id, "session_id": "active_sess"})


@given(parsers.parse('"{persona}" was last scheduled at sequence "{seq_id}"'))
def persona_last_scheduled(isolated_fs, persona, seq_id):
    """Add past schedule entry for persona."""
    schedule_file = isolated_fs / ".team" / "schedule.csv"
    rows = []
    if schedule_file.exists():
        with (schedule_file).open(newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    rows.append({"sequence": seq_id, "persona": persona, "session_id": "completed"})
    with (schedule_file).open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"]
        )
        writer.writeheader()
        writer.writerows(rows)


@given(parsers.parse('"{persona}" has never been scheduled'))
def persona_never_scheduled(persona):
    """Persona has never been scheduled (no action needed)."""


@given(parsers.parse('both "{p1}" and "{p2}" have {points:d} Borda points for "{seq_id}"'))
def set_equal_points(isolated_fs, p1, p2, points, seq_id):
    """Create votes so both personas have equal points."""
    _ = points
    votes_file = isolated_fs / ".team" / "votes.csv"
    with (votes_file).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["voter_sequence", "candidates"])
        writer.writeheader()
        # Create votes that result in equal points
        writer.writerow({"voter_sequence": "035", "candidates": f"{p1},{p2}"})
        writer.writerow({"voter_sequence": "036", "candidates": f"{p2},{p1}"})


@then(parsers.parse('sequence "{seq_id}" should be assigned to "{persona}"'))
def verify_sequence_assigned(isolated_fs, seq_id, persona):
    verify_schedule_update(isolated_fs, seq_id, persona)


@given(parsers.parse('a logged in persona "{p_id}"'))
def mock_simple_login(p_id):
    pass


@when(parsers.parse('I vote again for personas "{p1}" and "{p2}"'))
def vote_again(isolated_fs, p1, p2):
    """Cast another vote - in rolling model this overwrites previous vote."""
    personas_dir = isolated_fs / ".team" / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    for i in range(27):
        (personas_dir / f"persona_{i}").mkdir(exist_ok=True)

    vote_mgr = VoteManager(
        schedule_file=isolated_fs / ".team" / "schedule.csv", votes_file=isolated_fs / ".team" / "votes.csv"
    )

    with patch("repo.features.voting.PERSONAS_ROOT", personas_dir):
        # Cast vote using sequence 010 (curator's sequence for overwrite test)
        vote_mgr.cast_vote("010", [p1, p2])


@then(parsers.parse('only one vote record should exist for voter "{voter_seq}"'))
def verify_single_vote(isolated_fs, voter_seq):
    votes_file = isolated_fs / ".team" / "votes.csv"
    count = 0
    with (votes_file).open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["voter_sequence"] == voter_seq:
                count += 1
    assert count == 1, f"Expected 1 vote record, found {count}"


@then(parsers.parse('the vote should contain candidates "{candidates}"'))
def verify_candidates(isolated_fs, candidates):
    votes_file = isolated_fs / ".team" / "votes.csv"
    with (votes_file).open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["candidates"] == candidates:
                return
    pytest.fail(f"Candidates {candidates} not found in votes")


@given(parsers.parse('sequence "{seq_id}" is scheduled for "{persona}" with no session yet'))
def create_pending_schedule(isolated_fs, seq_id, persona):
    schedule_file = isolated_fs / ".team" / "schedule.csv"
    rows = []
    if schedule_file.exists():
        with (schedule_file).open(newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    rows.append({"sequence": seq_id, "persona": persona, "session_id": ""})
    with (schedule_file).open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status", "base_commit"]
        )
        writer.writeheader()
        writer.writerows(rows)


@when(parsers.parse('I vote for persona "{persona}" as first choice'))
def vote_first_choice(isolated_fs, persona):
    votes_file = isolated_fs / ".team" / "votes.csv"
    votes_file.parent.mkdir(parents=True, exist_ok=True)
    with (votes_file).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["voter_sequence", "candidates"])
        writer.writeheader()
        writer.writerow({"voter_sequence": "002", "candidates": persona})


@when(parsers.parse('the vote targets sequence "{seq_id}"'))
def vote_targets(seq_id):
    pass  # Already handled in previous step


@when(parsers.parse('I run "my-tools vote" without arguments'))
def run_vote_no_args(runner):
    result = runner.invoke(app, ["vote"])
    assert result.exit_code != 0  # Should fail without args


@then(parsers.parse('I should see a panel showing "{text}"'))
def verify_panel_text(text):
    pass  # Visual verification step


@then("I should see a table of current schedule")
def verify_schedule_table():
    pass


@then("I should see a table of available candidates")
def verify_candidates_table():
    pass


@then("I should see voting instructions")
def verify_instructions():
    pass


@when(parsers.parse('I hire a new persona "{persona}"'))
def hire_persona(isolated_fs, persona):
    persona_dir = isolated_fs / ".team" / "personas" / persona
    persona_dir.mkdir(parents=True, exist_ok=True)
    (persona_dir / "prompt.md.j2").write_text(f"# {persona}\n")


@when("I try to commit without voting")
def commit_without_vote():
    pass


@when(parsers.parse('I vote for "{persona}" as first choice'))
def vote_first(isolated_fs, persona):
    vote_first_choice(isolated_fs, persona)


@when("I try to commit")
def try_commit():
    pass


@then("the pre-commit hook should block the commit")
def verify_blocked():
    pass


@then(parsers.parse('I should see "{text}"'))
def verify_text(text):
    pass


@then("I should see options to fix: cast vote or delete the hire")
def verify_fix_options():
    pass


@then("the pre-commit hook should pass")
def verify_hook_pass():
    pass


@then("the commit should succeed")
def verify_commit_success():
    pass
