"""Tests for runs table schema (Priority D.1)."""

import duckdb
import pytest

from egregora.database.runs_schema import (
    RUNS_TABLE_DDL,
    RUNS_TABLE_SCHEMA,
    create_runs_table,
    drop_runs_table,
    ensure_runs_table_exists,
)


class TestRunsTableSchema:
    """Tests for RUNS_TABLE_SCHEMA."""

    def test_schema_has_required_columns(self):
        """Test that schema defines all required columns."""
        required_columns = {
            "run_id",
            "tenant_id",
            "stage",
            "status",
            "error",
            "input_fingerprint",
            "code_ref",
            "config_hash",
            "started_at",
            "finished_at",
            "rows_in",
            "rows_out",
            "duration_seconds",
            "llm_calls",
            "tokens",
            "trace_id",
        }
        assert set(RUNS_TABLE_SCHEMA.names) == required_columns

    def test_schema_column_types(self):
        """Test that schema columns have correct types."""
        from ibis.expr.datatypes import UUID, Float64, Int64, String, Timestamp

        schema = RUNS_TABLE_SCHEMA

        # UUID type
        assert isinstance(schema["run_id"], UUID)

        # Multi-tenant
        assert isinstance(schema["tenant_id"], String)
        assert schema["tenant_id"].nullable is True

        # String types
        assert isinstance(schema["stage"], String)
        assert isinstance(schema["status"], String)
        assert isinstance(schema["error"], String)
        assert schema["error"].nullable is True

        # Fingerprint columns
        assert isinstance(schema["input_fingerprint"], String)
        assert schema["input_fingerprint"].nullable is True
        assert isinstance(schema["code_ref"], String)
        assert schema["code_ref"].nullable is True
        assert isinstance(schema["config_hash"], String)
        assert schema["config_hash"].nullable is True

        # Timestamp types
        assert isinstance(schema["started_at"], Timestamp)
        assert schema["started_at"].timezone == "UTC"
        assert isinstance(schema["finished_at"], Timestamp)
        assert schema["finished_at"].timezone == "UTC"
        assert schema["finished_at"].nullable is True

        # Numeric types
        assert isinstance(schema["rows_in"], Int64)
        assert schema["rows_in"].nullable is True
        assert isinstance(schema["rows_out"], Int64)
        assert schema["rows_out"].nullable is True
        assert isinstance(schema["duration_seconds"], Float64)
        assert schema["duration_seconds"].nullable is True
        assert isinstance(schema["llm_calls"], Int64)
        assert schema["llm_calls"].nullable is True
        assert isinstance(schema["tokens"], Int64)
        assert schema["tokens"].nullable is True

        # Observability
        assert isinstance(schema["trace_id"], String)
        assert schema["trace_id"].nullable is True


class TestCreateRunsTable:
    """Tests for create_runs_table()."""

    def test_create_runs_table_success(self):
        """Test that create_runs_table() creates table successfully."""
        conn = duckdb.connect(":memory:")
        create_runs_table(conn)

        # Verify table exists
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
        ).fetchone()
        assert result[0] == 1

        # Verify table is empty
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()
        assert count[0] == 0

    def test_create_runs_table_with_indexes(self):
        """Test that create_runs_table() creates indexes."""
        conn = duckdb.connect(":memory:")
        create_runs_table(conn)

        # Check indexes exist
        indexes = conn.execute(
            """
            SELECT index_name FROM duckdb_indexes()
            WHERE table_name = 'runs'
            """
        ).fetchall()

        index_names = {row[0] for row in indexes}
        expected_indexes = {
            "idx_runs_started_at",
            "idx_runs_stage",
            "idx_runs_status",
            "idx_runs_fingerprint",
        }

        assert expected_indexes.issubset(index_names)

    def test_create_runs_table_idempotent(self):
        """Test that create_runs_table() is idempotent (CREATE IF NOT EXISTS)."""
        conn = duckdb.connect(":memory:")

        # Create table twice
        create_runs_table(conn)
        create_runs_table(conn)  # Should not raise

        # Table should still exist
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
        ).fetchone()
        assert result[0] == 1


class TestEnsureRunsTableExists:
    """Tests for ensure_runs_table_exists()."""

    def test_ensure_runs_table_creates_if_missing(self):
        """Test that ensure_runs_table_exists() creates table if missing."""
        conn = duckdb.connect(":memory:")
        ensure_runs_table_exists(conn)

        # Verify table exists
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
        ).fetchone()
        assert result[0] == 1

    def test_ensure_runs_table_idempotent(self):
        """Test that ensure_runs_table_exists() is safe to call multiple times."""
        conn = duckdb.connect(":memory:")

        # Call multiple times
        ensure_runs_table_exists(conn)
        ensure_runs_table_exists(conn)
        ensure_runs_table_exists(conn)

        # Table should still exist
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
        ).fetchone()
        assert result[0] == 1

    def test_ensure_runs_table_doesnt_drop_data(self):
        """Test that ensure_runs_table_exists() doesn't drop existing data."""
        conn = duckdb.connect(":memory:")
        ensure_runs_table_exists(conn)

        # Insert test data
        conn.execute(
            """
            INSERT INTO runs (
                run_id, stage, status, input_fingerprint, started_at
            ) VALUES (
                'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
                'test_stage',
                'completed',
                'sha256:abc123',
                '2025-01-09 10:00:00+00'
            )
            """
        )

        # Call ensure again
        ensure_runs_table_exists(conn)

        # Data should still be there
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()
        assert count[0] == 1


class TestDropRunsTable:
    """Tests for drop_runs_table()."""

    def test_drop_runs_table_success(self):
        """Test that drop_runs_table() drops table successfully."""
        conn = duckdb.connect(":memory:")
        create_runs_table(conn)

        # Verify table exists
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
        ).fetchone()
        assert result[0] == 1

        # Drop table
        drop_runs_table(conn)

        # Verify table is gone
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
        ).fetchone()
        assert result[0] == 0

    def test_drop_runs_table_idempotent(self):
        """Test that drop_runs_table() is idempotent (DROP IF EXISTS)."""
        conn = duckdb.connect(":memory:")
        create_runs_table(conn)

        # Drop multiple times
        drop_runs_table(conn)
        drop_runs_table(conn)  # Should not raise


class TestRunsTableDDL:
    """Tests for RUNS_TABLE_DDL."""

    def test_ddl_creates_valid_table(self):
        """Test that DDL string creates a valid table."""
        conn = duckdb.connect(":memory:")
        conn.execute(RUNS_TABLE_DDL)

        # Verify table exists
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
        ).fetchone()
        assert result[0] == 1

    def test_ddl_enforces_status_constraint(self):
        """Test that DDL enforces status CHECK constraint."""
        conn = duckdb.connect(":memory:")
        conn.execute(RUNS_TABLE_DDL)

        # Valid status should work
        conn.execute(
            """
            INSERT INTO runs (
                run_id, stage, status, input_fingerprint, started_at
            ) VALUES (
                'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
                'test',
                'completed',
                'sha256:abc',
                '2025-01-09 10:00:00+00'
            )
            """
        )

        # Invalid status should fail
        with pytest.raises(Exception, match="Constraint Error|CHECK constraint"):
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, stage, status, input_fingerprint, started_at
                ) VALUES (
                    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
                    'test',
                    'invalid_status',
                    'sha256:def',
                    '2025-01-09 10:00:00+00'
                )
                """
            )

    def test_ddl_enforces_primary_key(self):
        """Test that DDL enforces run_id PRIMARY KEY constraint."""
        conn = duckdb.connect(":memory:")
        conn.execute(RUNS_TABLE_DDL)

        # Insert first row
        conn.execute(
            """
            INSERT INTO runs (
                run_id, stage, status, input_fingerprint, started_at
            ) VALUES (
                'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
                'test',
                'completed',
                'sha256:abc',
                '2025-01-09 10:00:00+00'
            )
            """
        )

        # Duplicate run_id should fail
        with pytest.raises(Exception, match="Constraint Error|PRIMARY KEY"):
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, stage, status, input_fingerprint, started_at
                ) VALUES (
                    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
                    'test2',
                    'failed',
                    'sha256:def',
                    '2025-01-09 11:00:00+00'
                )
                """
            )
