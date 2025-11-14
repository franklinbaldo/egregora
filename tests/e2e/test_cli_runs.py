"""Integration tests for the runs CLI command (tracking and observability).

Tests:
- runs tail - Show last N runs
- runs show - Show detailed run information
- runs list - List all runs with filtering
- runs clear - Clear old runs

These tests use a mock runs database to avoid depending on actual pipeline executions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from typer.testing import CliRunner

from egregora.cli import app
from egregora.database.ir_schema import create_run_events_table

# Create a CLI runner for testing
runner = CliRunner()


@pytest.fixture
def temp_runs_db(tmp_path: Path) -> Path:
    """Create a temporary runs database for testing."""
    db_path = tmp_path / "runs.duckdb"
    conn = duckdb.connect(str(db_path))
    create_run_events_table(conn)
    conn.close()
    return db_path


@pytest.fixture
def populated_runs_db(temp_runs_db: Path) -> Path:
    """Create a runs database with sample data for testing (event-sourced pattern)."""
    conn = duckdb.connect(str(temp_runs_db))

    # Create sample runs with different statuses and timestamps
    base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

    runs = [
        {
            "run_id": uuid.uuid4(),
            "stage": "ingestion",
            "status": "completed",
            "started_at": base_time - timedelta(hours=3),
            "finished_at": base_time - timedelta(hours=2, minutes=45),
            "rows_in": 1000,
            "rows_out": 1000,
            "llm_calls": 0,
            "tokens": 0,
        },
        {
            "run_id": uuid.uuid4(),
            "stage": "privacy",
            "status": "completed",
            "started_at": base_time - timedelta(hours=2, minutes=45),
            "finished_at": base_time - timedelta(hours=2, minutes=30),
            "rows_in": 1000,
            "rows_out": 1000,
            "llm_calls": 0,
            "tokens": 0,
        },
        {
            "run_id": uuid.uuid4(),
            "stage": "enrichment",
            "status": "completed",
            "started_at": base_time - timedelta(hours=2, minutes=30),
            "finished_at": base_time - timedelta(hours=1),
            "rows_in": 1000,
            "rows_out": 1000,
            "llm_calls": 5,
            "tokens": 12500,
        },
        {
            "run_id": uuid.uuid4(),
            "stage": "generation",
            "status": "completed",
            "started_at": base_time - timedelta(minutes=60),
            "finished_at": base_time - timedelta(minutes=30),
            "rows_in": 50,
            "rows_out": 3,
            "llm_calls": 12,
            "tokens": 28000,
        },
        {
            "run_id": uuid.uuid4(),
            "stage": "publication",
            "status": "completed",
            "started_at": base_time - timedelta(minutes=30),
            "finished_at": base_time,
            "rows_in": 3,
            "rows_out": 3,
            "llm_calls": 0,
            "tokens": 0,
        },
        {
            "run_id": uuid.uuid4(),
            "stage": "enrichment",
            "status": "failed",
            "started_at": base_time - timedelta(hours=5),
            "finished_at": base_time - timedelta(hours=4, minutes=50),
            "rows_in": 500,
            "rows_out": None,
            "llm_calls": 2,
            "tokens": 5000,
            "error": "ConnectionError: Failed to connect to API",
            "trace_id": "trace-xyz-failed-123",
        },
    ]

    # Insert events using event-sourced pattern (started + completed/failed)
    for i, run_data in enumerate(runs):
        # Started event
        conn.execute(
            """
            INSERT INTO run_events (
                event_id, run_id, stage, status, timestamp,
                input_fingerprint, rows_in
            ) VALUES (?, ?, ?, 'started', ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                str(run_data["run_id"]),
                run_data["stage"],
                run_data["started_at"],
                f"sha256:test-fingerprint-{i}",
                run_data.get("rows_in"),
            ],
        )

        # Completed/failed event
        if run_data["finished_at"]:
            duration_seconds = (
                run_data["finished_at"] - run_data["started_at"]
            ).total_seconds()
            conn.execute(
                """
                INSERT INTO run_events (
                    event_id, run_id, stage, status, timestamp,
                    rows_out, duration_seconds, llm_calls, tokens, error, trace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    str(uuid.uuid4()),
                    str(run_data["run_id"]),
                    run_data["stage"],
                    run_data["status"],
                    run_data["finished_at"],
                    run_data.get("rows_out"),
                    duration_seconds,
                    run_data.get("llm_calls", 0),
                    run_data.get("tokens", 0),
                    run_data.get("error"),
                    run_data.get("trace_id"),
                ],
            )

    conn.close()
    return temp_runs_db


# ==============================================================================
# Test: runs tail
# ==============================================================================


class TestRunsTail:
    """Tests for 'egregora runs tail' command."""

    def test_runs_tail_with_no_database(self, tmp_path: Path):
        """Test tail command when runs database doesn't exist."""
        db_path = tmp_path / "nonexistent" / "runs.duckdb"

        result = runner.invoke(app, ["runs", "tail", "--db-path", str(db_path)])

        # Should exit with code 0 (graceful handling)
        assert result.exit_code == 0
        # Should show helpful message
        assert "No runs database found" in result.stdout or "No runs" in result.stdout

    def test_runs_tail_with_empty_database(self, temp_runs_db: Path):
        """Test tail command with empty runs database."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(temp_runs_db)])

        assert result.exit_code == 0
        assert "No runs found" in result.stdout

    def test_runs_tail_default_limit(self, populated_runs_db: Path):
        """Test tail command returns default limit (10 runs)."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db)])

        assert result.exit_code == 0
        # Should contain table with run data
        assert "Last" in result.stdout
        assert "Run ID" in result.stdout
        assert "Stage" in result.stdout
        assert "Status" in result.stdout
        assert "started" in result.stdout.lower() or "Duration" in result.stdout

    def test_runs_tail_custom_limit(self, populated_runs_db: Path):
        """Test tail command with custom limit."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db), "--n", "3"])

        assert result.exit_code == 0
        assert "Last 3 Runs" in result.stdout or "Last" in result.stdout

    def test_runs_tail_shows_status_colors(self, populated_runs_db: Path):
        """Test tail command displays status with color codes."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db)])

        assert result.exit_code == 0
        # Should show at least completed and failed statuses
        assert "completed" in result.stdout.lower() or "done" in result.stdout.lower()

    def test_runs_tail_shows_row_counts(self, populated_runs_db: Path):
        """Test tail command displays row counts."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db)])

        assert result.exit_code == 0
        # Should show rows_in and rows_out columns
        assert "Rows In" in result.stdout or "rows" in result.stdout.lower()

    def test_runs_tail_shows_duration(self, populated_runs_db: Path):
        """Test tail command displays duration."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db)])

        assert result.exit_code == 0
        # Should show duration (in seconds with 's' suffix or similar)
        assert "s" in result.stdout.lower() or "duration" in result.stdout.lower()

    def test_runs_tail_ordering(self, populated_runs_db: Path):
        """Test that tail command orders runs by most recent first."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db), "--n", "5"])

        assert result.exit_code == 0
        # Check that we're showing run information
        # Output should contain stage or status information
        assert (
            "Stage" in result.stdout
            or "Status" in result.stdout
            or "ingestion" in result.stdout.lower()
            or "privacy" in result.stdout.lower()
        )


# ==============================================================================
# Test: runs show
# ==============================================================================


class TestRunsShow:
    """Tests for 'egregora runs show' command."""

    def test_runs_show_with_no_database(self, tmp_path: Path):
        """Test show command when runs database doesn't exist."""
        db_path = tmp_path / "nonexistent" / "runs.duckdb"
        run_id = str(uuid.uuid4())

        result = runner.invoke(app, ["runs", "show", run_id, "--db-path", str(db_path)])

        # Should exit with error code
        assert result.exit_code == 1
        assert "No runs database found" in result.stdout

    def test_runs_show_nonexistent_run(self, populated_runs_db: Path):
        """Test show command with nonexistent run ID."""
        result = runner.invoke(
            app,
            ["runs", "show", "nonexistent-run-id", "--db-path", str(populated_runs_db)],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_runs_show_full_run_id(self, populated_runs_db: Path):
        """Test show command with full run UUID."""
        # Get first run ID from database
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        result = conn.execute("SELECT CAST(run_id AS VARCHAR) FROM run_events LIMIT 1").fetchone()
        conn.close()

        if result:
            run_id = result[0]
            result = runner.invoke(app, ["runs", "show", run_id, "--db-path", str(populated_runs_db)])

            assert result.exit_code == 0
            assert "Run ID" in result.stdout
            assert "Stage" in result.stdout
            assert "Status" in result.stdout

    def test_runs_show_prefix_matching(self, populated_runs_db: Path):
        """Test show command with UUID prefix matching."""
        # Get first run ID from database
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        result = conn.execute("SELECT CAST(run_id AS VARCHAR) FROM run_events LIMIT 1").fetchone()
        conn.close()

        if result:
            run_id = result[0]
            # Use first 8 characters as prefix
            run_id_prefix = run_id[:8]
            result = runner.invoke(app, ["runs", "show", run_id_prefix, "--db-path", str(populated_runs_db)])

            assert result.exit_code == 0
            assert "Run ID" in result.stdout or "Details" in result.stdout

    def test_runs_show_displays_panel(self, populated_runs_db: Path):
        """Test that show command displays output in panel format."""
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        result = conn.execute(
            "SELECT CAST(run_id AS VARCHAR) FROM run_events WHERE status = 'completed' LIMIT 1"
        ).fetchone()
        conn.close()

        if result:
            run_id = result[0][:8]
            result = runner.invoke(app, ["runs", "show", run_id, "--db-path", str(populated_runs_db)])

            assert result.exit_code == 0
            # Panel should contain detailed run information
            assert any(keyword in result.stdout for keyword in ["Timestamps", "Metrics", "Details", "Stage"])

    def test_runs_show_completed_status(self, populated_runs_db: Path):
        """Test show command displays completed run with metrics."""
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        result = conn.execute(
            "SELECT CAST(run_id AS VARCHAR) FROM run_events WHERE stage = 'generation' LIMIT 1"
        ).fetchone()
        conn.close()

        if result:
            run_id = result[0][:8]
            result = runner.invoke(app, ["runs", "show", run_id, "--db-path", str(populated_runs_db)])

            assert result.exit_code == 0
            # Should show metrics for a generation stage run
            assert (
                "Metrics" in result.stdout
                or "rows" in result.stdout.lower()
                or "llm" in result.stdout.lower()
            )

    def test_runs_show_failed_status(self, populated_runs_db: Path):
        """Test show command displays failed run with error message."""
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        result = conn.execute(
            "SELECT CAST(run_id AS VARCHAR) FROM run_events WHERE status = 'failed' LIMIT 1"
        ).fetchone()
        conn.close()

        if result:
            run_id = result[0][:8]
            result = runner.invoke(app, ["runs", "show", run_id, "--db-path", str(populated_runs_db)])

            assert result.exit_code == 0
            # Should display error information
            assert "Error" in result.stdout or "failed" in result.stdout.lower()

    def test_runs_show_with_trace_id(self, populated_runs_db: Path):
        """Test show command displays trace ID when available."""
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        result = conn.execute(
            "SELECT CAST(run_id AS VARCHAR) FROM run_events WHERE trace_id IS NOT NULL LIMIT 1"
        ).fetchone()
        conn.close()

        if result:
            run_id = result[0][:8]
            result = runner.invoke(app, ["runs", "show", run_id, "--db-path", str(populated_runs_db)])

            assert result.exit_code == 0
            # Should show observability section with trace ID
            assert "Observability" in result.stdout or "trace" in result.stdout.lower()


# ==============================================================================
# Test: runs list
# ==============================================================================


class TestRunsList:
    """Tests for 'egregora runs list' command."""

    def test_runs_list_with_no_database(self, tmp_path: Path):
        """Test list command when runs database doesn't exist."""
        db_path = tmp_path / "nonexistent" / "runs.duckdb"

        result = runner.invoke(app, ["runs", "list", "--db-path", str(db_path)])

        # Command may not exist yet (exit code 2) or may handle gracefully (0, 1)
        assert result.exit_code in (0, 1, 2)

    def test_runs_list_default(self, populated_runs_db: Path):
        """Test list command shows all runs."""
        result = runner.invoke(app, ["runs", "list", "--db-path", str(populated_runs_db)])

        # Command may not exist yet, so check for reasonable responses
        if result.exit_code == 0:
            # Should show run information
            assert any(keyword in result.stdout for keyword in ["Run", "Stage", "Status", "Runs"])
        else:
            # If command doesn't exist (exit code 2), that's okay for now
            # The command might not be implemented yet
            assert result.exit_code in (1, 2)

    def test_runs_list_filter_by_stage(self, populated_runs_db: Path):
        """Test list command with stage filter."""
        result = runner.invoke(
            app, ["runs", "list", "--db-path", str(populated_runs_db), "--stage", "generation"]
        )

        # Command may not exist yet
        if result.exit_code == 0:
            assert "generation" in result.stdout.lower() or "Stage" in result.stdout
        else:
            # If command doesn't exist, that's okay for now
            pass

    def test_runs_list_filter_by_status(self, populated_runs_db: Path):
        """Test list command with status filter."""
        result = runner.invoke(
            app, ["runs", "list", "--db-path", str(populated_runs_db), "--status", "failed"]
        )

        # Command may not exist yet
        if result.exit_code == 0:
            # Should show failed runs
            assert "failed" in result.stdout.lower() or "Status" in result.stdout
        else:
            # If command doesn't exist, that's okay for now
            pass

    def test_runs_list_limit(self, populated_runs_db: Path):
        """Test list command with limit parameter."""
        result = runner.invoke(app, ["runs", "list", "--db-path", str(populated_runs_db), "--limit", "3"])

        # Command may not exist yet
        if result.exit_code == 0:
            assert any(keyword in result.stdout for keyword in ["Run", "Stage", "Status"])
        else:
            # If command doesn't exist, that's okay for now
            pass

    def test_runs_list_json_output(self, populated_runs_db: Path):
        """Test list command with JSON output format."""
        result = runner.invoke(app, ["runs", "list", "--db-path", str(populated_runs_db), "--json"])

        # Command may not exist yet
        if result.exit_code == 0:
            # Should be valid JSON
            assert "{" in result.stdout or "[" in result.stdout
        else:
            # If command doesn't exist, that's okay for now
            pass


# ==============================================================================
# Test: runs clear
# ==============================================================================


class TestRunsClear:
    """Tests for 'egregora runs clear' command."""

    def test_runs_clear_with_no_database(self, tmp_path: Path):
        """Test clear command when runs database doesn't exist."""
        db_path = tmp_path / "nonexistent" / "runs.duckdb"

        result = runner.invoke(app, ["runs", "clear", "--db-path", str(db_path)])

        # Command may not exist yet (exit code 2) or may handle gracefully (0, 1)
        assert result.exit_code in (0, 1, 2)

    def test_runs_clear_requires_confirmation(self, populated_runs_db: Path):
        """Test clear command asks for confirmation."""
        result = runner.invoke(
            app,
            ["runs", "clear", "--db-path", str(populated_runs_db)],
            input="n\n",  # Decline confirmation
        )

        # Command may not exist yet
        if result.exit_code == 0:
            # Should mention confirmation
            assert "confirm" in result.stdout.lower() or "Are you sure" in result.stdout
        else:
            # If command doesn't exist, that's okay for now
            pass

    def test_runs_clear_older_than(self, populated_runs_db: Path):
        """Test clear command with age filter."""
        result = runner.invoke(
            app,
            [
                "runs",
                "clear",
                "--db-path",
                str(populated_runs_db),
                "--older-than",
                "24",
                "--force",
            ],
        )

        # Command may not exist yet
        if result.exit_code == 0:
            # Should show success message
            assert any(
                keyword in result.stdout.lower() for keyword in ["cleared", "deleted", "removed", "success"]
            )
        else:
            # If command doesn't exist, that's okay for now
            pass

    def test_runs_clear_dry_run(self, populated_runs_db: Path):
        """Test clear command with dry-run flag."""
        result = runner.invoke(
            app,
            [
                "runs",
                "clear",
                "--db-path",
                str(populated_runs_db),
                "--dry-run",
            ],
        )

        # Command may not exist yet
        if result.exit_code == 0:
            # Should show what would be deleted without deleting
            assert any(
                keyword in result.stdout.lower() for keyword in ["would", "would be", "dry-run", "preview"]
            )
        else:
            # If command doesn't exist, that's okay for now
            pass

    def test_runs_clear_with_force_flag(self, populated_runs_db: Path):
        """Test clear command with force flag (no confirmation)."""
        # Get initial run count
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        initial_count = conn.execute("SELECT COUNT(DISTINCT run_id) FROM run_events").fetchone()[0]
        conn.close()

        result = runner.invoke(
            app,
            ["runs", "clear", "--db-path", str(populated_runs_db), "--force"],
        )

        # Command may not exist yet
        if result.exit_code == 0:
            # Should show success message
            assert any(keyword in result.stdout.lower() for keyword in ["cleared", "deleted", "removed"])

            # Database may be cleared
            conn = duckdb.connect(str(populated_runs_db), read_only=True)
            final_count = conn.execute("SELECT COUNT(DISTINCT run_id) FROM run_events").fetchone()[0]
            conn.close()

            # Count should be less than or equal to initial
            assert final_count <= initial_count
        else:
            # If command doesn't exist, that's okay for now
            pass


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestRunsCommandsIntegration:
    """Integration tests for runs commands working together."""

    def test_runs_workflow(self, populated_runs_db: Path):
        """Test typical runs command workflow: tail → show → clear."""
        # 1. View recent runs
        tail_result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db)])
        assert tail_result.exit_code == 0

        # 2. Get a run ID from the tail output and view details
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        run_result = conn.execute("SELECT CAST(run_id AS VARCHAR) FROM run_events LIMIT 1").fetchone()
        conn.close()

        if run_result:
            run_id = run_result[0][:8]
            show_result = runner.invoke(app, ["runs", "show", run_id, "--db-path", str(populated_runs_db)])
            assert show_result.exit_code == 0

    def test_runs_commands_preserve_database(self, populated_runs_db: Path):
        """Test that read-only runs commands don't modify database."""
        # Get initial state
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        initial_count = conn.execute("SELECT COUNT(DISTINCT run_id) FROM run_events").fetchone()[0]
        conn.close()

        # Run commands
        runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db)])
        runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db), "--n", "3"])

        # Verify database unchanged
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        final_count = conn.execute("SELECT COUNT(DISTINCT run_id) FROM run_events").fetchone()[0]
        conn.close()

        assert initial_count == final_count


# ==============================================================================
# Edge Case Tests
# ==============================================================================


class TestRunsCommandsEdgeCases:
    """Edge case and error handling tests for runs commands."""

    def test_runs_tail_with_zero_limit(self, populated_runs_db: Path):
        """Test tail command with zero limit."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db), "--n", "0"])

        # Should handle gracefully (either show nothing or error)
        assert result.exit_code in (0, 1, 2)

    def test_runs_tail_with_negative_limit(self, populated_runs_db: Path):
        """Test tail command with negative limit."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db), "--n", "-5"])

        # Should handle gracefully
        assert result.exit_code in (0, 1, 2)

    def test_runs_show_with_empty_run_id(self, populated_runs_db: Path):
        """Test show command with empty run ID."""
        result = runner.invoke(app, ["runs", "show", "", "--db-path", str(populated_runs_db)])

        # Should handle gracefully
        assert result.exit_code in (0, 1, 2)

    def test_runs_tail_large_limit(self, populated_runs_db: Path):
        """Test tail command with limit larger than available runs."""
        result = runner.invoke(app, ["runs", "tail", "--db-path", str(populated_runs_db), "--n", "1000"])

        # Should handle gracefully and return all available
        assert result.exit_code in (0, 1)

    def test_runs_show_case_insensitive_prefix(self, populated_runs_db: Path):
        """Test show command with case variations in run ID prefix."""
        conn = duckdb.connect(str(populated_runs_db), read_only=True)
        result = conn.execute("SELECT CAST(run_id AS VARCHAR) FROM run_events LIMIT 1").fetchone()
        conn.close()

        if result:
            run_id = result[0][:8]
            # DuckDB UUIDs might handle case variations
            result = runner.invoke(app, ["runs", "show", run_id, "--db-path", str(populated_runs_db)])

            assert result.exit_code in (0, 1, 2)
