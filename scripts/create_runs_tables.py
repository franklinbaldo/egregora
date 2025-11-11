#!/usr/bin/env python3
"""Create runs and lineage tables in DuckDB.

This script initializes the observability and lineage tracking infrastructure.
Run this once per DuckDB database to create the required tables.

Usage:
    python scripts/create_runs_tables.py
    python scripts/create_runs_tables.py --db-path=path/to/database.duckdb
    python scripts/create_runs_tables.py --check  # Validate without creating

Examples:
    # Create tables in default location (.egregora-cache/runs.duckdb)
    python scripts/create_runs_tables.py

    # Create tables in custom location
    python scripts/create_runs_tables.py --db-path=./my-runs.duckdb

    # Check if tables exist (dry run)
    python scripts/create_runs_tables.py --check

Exit codes:
    0: Success (tables created or already exist)
    1: Error (SQL error, file not found, etc.)
    2: Check failed (tables don't exist or schema mismatch)

"""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

import duckdb


def read_sql_file(sql_path: Path) -> str:
    """Read SQL schema file.

    Args:
        sql_path: Path to .sql file

    Returns:
        SQL statements as string

    Raises:
        FileNotFoundError: If sql_path doesn't exist

    """
    if not sql_path.exists():
        raise FileNotFoundError(sql_path)

    return sql_path.read_text()


def create_tables(conn: duckdb.DuckDBPyConnection, schema_dir: Path) -> None:
    """Create runs and lineage tables.

    Args:
        conn: DuckDB connection
        schema_dir: Path to schema/ directory

    Raises:
        FileNotFoundError: If schema files missing
        duckdb.Error: If SQL execution fails

    """
    # Read schema files
    runs_sql = read_sql_file(schema_dir / "runs_v1.sql")
    lineage_sql = read_sql_file(schema_dir / "lineage_v1.sql")

    # Execute schema creation
    conn.execute(runs_sql)

    conn.execute(lineage_sql)


def check_tables(conn: duckdb.DuckDBPyConnection, *, silent: bool = False) -> bool:
    """Check if runs and lineage tables exist with correct schema.

    Args:
        conn: DuckDB connection
        silent: If True, suppress error messages (default: False)

    Returns:
        True if tables exist and have correct schema, False otherwise

    """
    # Check if tables exist
    result = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name IN ('runs', 'lineage')
        ORDER BY table_name
    """).fetchall()

    table_names = {row[0] for row in result}

    if "runs" not in table_names:
        if not silent:
            pass
        return False

    if "lineage" not in table_names:
        if not silent:
            pass
        return False

    # Validate runs table schema
    runs_columns = conn.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = 'runs'
        ORDER BY ordinal_position
    """).fetchall()

    required_runs_columns = {
        "run_id",
        "stage",
        "tenant_id",
        "started_at",
        "finished_at",
        "input_fingerprint",
        "code_ref",
        "config_hash",
        "rows_in",
        "rows_out",
        "llm_calls",
        "tokens",
        "status",
        "error",
        "trace_id",
    }

    actual_runs_columns = {col[0] for col in runs_columns}

    if not required_runs_columns.issubset(actual_runs_columns):
        required_runs_columns - actual_runs_columns
        return False

    # Validate lineage table schema
    lineage_columns = conn.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = 'lineage'
        ORDER BY ordinal_position
    """).fetchall()

    required_lineage_columns = {"child_run_id", "parent_run_id"}
    actual_lineage_columns = {col[0] for col in lineage_columns}

    if not required_lineage_columns.issubset(actual_lineage_columns):
        required_lineage_columns - actual_lineage_columns
        return False

    return True


def main() -> NoReturn:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create runs and lineage tables in DuckDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(".egregora-cache/runs.duckdb"),
        help="Path to DuckDB database (default: .egregora-cache/runs.duckdb)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if tables exist without creating (dry run)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop existing tables before creating (destructive!)",
    )

    args = parser.parse_args()

    # Ensure parent directory exists
    args.db_path.parent.mkdir(parents=True, exist_ok=True)

    # Find schema directory
    script_dir = Path(__file__).parent
    schema_dir = script_dir.parent / "schema"

    if not schema_dir.exists():
        sys.exit(1)

    # Connect to DuckDB
    conn = duckdb.connect(str(args.db_path))

    try:
        if args.check:
            # Dry run: check if tables exist
            if check_tables(conn):
                sys.exit(0)
            else:
                sys.exit(2)

        # Check if tables already exist (silent mode - we'll create them if missing)
        if check_tables(conn, silent=True):
            if args.force:
                conn.execute("DROP TABLE IF EXISTS lineage")
                conn.execute("DROP TABLE IF EXISTS runs")
            else:
                sys.exit(0)

        # Create tables
        create_tables(conn, schema_dir)

        # Validate creation
        if check_tables(conn):
            sys.exit(0)
        else:
            sys.exit(1)

    except FileNotFoundError:
        sys.exit(1)
    except duckdb.Error:
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
