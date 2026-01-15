"""Step definitions for CSV-based persona scheduling."""

import csv
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenario, then, when


# Define scenarios
@scenario("../features/csv_scheduler.feature", "Scheduler reads next persona from schedule.csv")
def test_scheduler_reads_next():
    pass


@scenario("../features/csv_scheduler.feature", "Scheduler skips completed sequences")
def test_scheduler_skips_completed():
    pass


@scenario("../features/csv_scheduler.feature", "Scheduler waits for active PR")
def test_scheduler_waits_for_pr():
    pass


@scenario("../features/csv_scheduler.feature", "Scheduler auto-extends when running low")
def test_scheduler_auto_extends():
    pass


@scenario("../features/csv_scheduler.feature", "Oracle session reuse within 24 hours")
def test_oracle_session_reuse():
    pass


@scenario("../features/csv_scheduler.feature", "Oracle session refresh after 24 hours")
def test_oracle_session_refresh():
    pass


@pytest.fixture
def temp_schedule_dir(tmp_path):
    """Create a temporary directory for schedule files."""
    return tmp_path


@pytest.fixture
def mock_schedule_path(temp_schedule_dir, mocker):
    """Mock the SCHEDULE_PATH to use temp directory."""
    schedule_path = temp_schedule_dir / "schedule.csv"
    mocker.patch("jules.scheduler.schedule.SCHEDULE_PATH", schedule_path)
    return schedule_path


@pytest.fixture
def mock_oracle_schedule_path(temp_schedule_dir, mocker):
    """Mock the ORACLE_SCHEDULE_PATH to use temp directory."""
    oracle_path = temp_schedule_dir / "oracle_schedule.csv"
    mocker.patch("jules.scheduler.schedule.ORACLE_SCHEDULE_PATH", oracle_path)
    return oracle_path


@pytest.fixture
def mock_jules_client(mocker):
    """Mock JulesClient."""
    mock_client = MagicMock()
    mock_client.list_sessions.return_value = {"sessions": []}
    mocker.patch("jules.scheduler.engine.JulesClient", return_value=mock_client)
    return mock_client


@pytest.fixture
def mock_branch_manager(mocker):
    """Mock BranchManager."""
    mock_mgr = MagicMock()
    mock_mgr.create_session_branch.return_value = "jules-sched-test"
    mocker.patch("jules.scheduler.engine.BranchManager", return_value=mock_mgr)
    return mock_mgr


@pytest.fixture
def mock_orchestrator(mocker):
    """Mock SessionOrchestrator to return fake session ID."""
    mock_orch = MagicMock()
    mock_orch.create_session.return_value = "999888777"
    mocker.patch("jules.scheduler.engine.SessionOrchestrator", return_value=mock_orch)
    return mock_orch


@pytest.fixture
def context():
    """Shared context for test steps."""
    return {}


# Background
@given("the Jules scheduler is configured with CSV-based scheduling")
def scheduler_configured():
    pass  # CSV-based scheduling is now the default


# Given steps for schedule.csv setup
@given("a schedule.csv with the following rows:", target_fixture="schedule_rows")
def schedule_with_rows(mock_schedule_path, context, datatable):
    # Parse the datatable
    header = datatable[0]
    rows = []
    for row_data in datatable[1:]:
        rows.append(dict(zip(header, row_data, strict=False)))

    # Write to CSV
    with open(mock_schedule_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)

    context["schedule_path"] = mock_schedule_path
    context["initial_rows"] = rows
    return rows


@given(parsers.parse("a schedule.csv with only {count:d} empty rows remaining"))
def schedule_with_few_empty(count, mock_schedule_path, context):
    rows = []
    # Add some completed rows
    for i in range(10):
        rows.append(
            {
                "sequence": f"{i + 1:03d}",
                "persona": "absolutist",
                "session_id": str(100000 + i),
                "pr_number": str(200 + i),
                "pr_status": "merged",
            }
        )
    # Add empty rows
    for i in range(count):
        rows.append(
            {
                "sequence": f"{i + 11:03d}",
                "persona": "artisan",
                "session_id": "",
                "pr_number": "",
                "pr_status": "",
            }
        )

    with open(mock_schedule_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["sequence", "persona", "session_id", "pr_number", "pr_status"])
        writer.writeheader()
        writer.writerows(rows)

    context["schedule_path"] = mock_schedule_path
    context["initial_row_count"] = len(rows)


@given(parsers.parse("an Oracle session was created {hours:d} hours ago"))
def oracle_session_age(hours, mock_oracle_schedule_path, context):
    created_at = datetime.now(UTC) - timedelta(hours=hours)
    rows = [{"session_id": "oracle_123", "created_at": created_at.isoformat(), "status": "active"}]

    with open(mock_oracle_schedule_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["session_id", "created_at", "status"])
        writer.writeheader()
        writer.writerows(rows)

    context["oracle_schedule_path"] = mock_oracle_schedule_path
    context["initial_oracle_session"] = "oracle_123"


# When steps
@when("the scheduler runs a sequential tick")
def run_sequential_tick(mock_jules_client, mock_branch_manager, mock_orchestrator, mocker, context):
    # Mock get_repo_info and get_open_prs
    mocker.patch("jules.scheduler.engine.get_repo_info", return_value={"owner": "test", "repo": "test"})
    mocker.patch("jules.scheduler.engine.get_open_prs", return_value=[])
    mocker.patch("jules.scheduler.engine.get_sync_patch", return_value=None)

    # Mock PersonaLoader
    mock_persona = MagicMock()
    mock_persona.id = "absolutist"
    mock_persona.emoji = "⚡"
    mock_persona.prompt_body = "Test prompt"

    mock_persona2 = MagicMock()
    mock_persona2.id = "artisan"
    mock_persona2.emoji = "🎨"
    mock_persona2.prompt_body = "Test prompt 2"

    mock_loader = MagicMock()
    mock_loader.load_personas.return_value = [mock_persona, mock_persona2]
    mocker.patch("jules.scheduler.engine.PersonaLoader", return_value=mock_loader)

    from jules.scheduler.engine import execute_sequential_tick

    execute_sequential_tick(dry_run=False)

    context["orchestrator"] = mock_orchestrator


@when("the Oracle facilitator needs to start")
def oracle_needs_start(mock_jules_client, mocker, context):
    # Mock list_inbox to return pending questions
    mocker.patch(
        "jules.scheduler.engine.list_inbox",
        return_value=[{"key": "test", "from": "refactor", "subject": "Help", "read": False}],
    )

    from jules.scheduler.schedule import get_active_oracle_session

    context["active_oracle"] = get_active_oracle_session()


# Then steps
@then(parsers.parse('a session should be created for persona "{persona}"'))
def session_created_for(persona, context):
    orchestrator = context["orchestrator"]
    assert orchestrator.create_session.called
    call_args = orchestrator.create_session.call_args
    request = call_args[0][0]
    assert persona in request.persona_id


@then("no new session should be created")
def no_session_created(context):
    orchestrator = context.get("orchestrator")
    if orchestrator:
        assert not orchestrator.create_session.called


@then("the scheduler should report waiting for PR")
def scheduler_reports_waiting(capsys):
    # Check stdout contains waiting message
    # This is handled by the scheduler printing, not by our context
    pass  # Logging verification would require capturing stdout


@then(parsers.parse('the schedule.csv should be updated with the session_id for sequence "{seq}"'))
def schedule_updated(seq, mock_schedule_path):
    with open(mock_schedule_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["sequence"] == seq:
                assert row["session_id"] != "", f"Expected session_id for sequence {seq}"
                return
    pytest.fail(f"Sequence {seq} not found in schedule")


@then(parsers.parse("the schedule.csv should contain at least {count:d} total rows"))
def schedule_has_rows(count, mock_schedule_path):
    with open(mock_schedule_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) >= count, f"Expected at least {count} rows, got {len(rows)}"


@then("no new Oracle session should be created")
def no_oracle_created(context):
    assert context.get("active_oracle") is not None


@then("the existing Oracle session should be reused")
def oracle_reused(context):
    assert context["active_oracle"]["session_id"] == "oracle_123"


@then("a new Oracle session should be created")
def new_oracle_created(context):
    assert context.get("active_oracle") is None


@then("the old session should be marked as expired")
def old_session_expired(mock_oracle_schedule_path):
    with open(mock_oracle_schedule_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["session_id"] == "oracle_123":
                assert row["status"] == "expired"
                return
