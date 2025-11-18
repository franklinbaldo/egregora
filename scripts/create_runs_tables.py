#!/usr/bin/env python3
"""Create runs table in DuckDB.

This script initializes the observability and tracking infrastructure.
Run this once per DuckDB database to create the required table.

NOTE: As of 2025-11-17, the separate lineage table was removed.
Lineage is now tracked via the parent_run_id column in the runs table.

Usage:
    python scripts/create_runs_tables.py
    python scripts/create_runs_tables.py --db-path=path/to/database.duckdb
    python scripts/create_runs_tables.py --check  # Validate without creating

Examples:
    # Create table in default location (.egregora-cache/runs.duckdb)
    python scripts/create_runs_tables.py

    # Create table in custom location
    python scripts/create_runs_tables.py --db-path=./my-runs.duckdb

    # Check if table exists (dry run)
    python scripts/create_runs_tables.py --check

Exit codes:
    0: Success (table created or already exists)
    1: Error (SQL error, file not found, etc.)
    2: Check failed (table doesn't exist or schema mismatch)

"""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

import duckdb

from egregora.database.ir_schema import RUNS_TABLE_DDL, RUNS_TABLE_SCHEMA


def create_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Create runs table using the canonical schema.

    Note: As of 2025-11-17, the separate lineage table was removed.
    Lineage is now tracked via parent_run_id column in runs table.

    Args:
        conn: DuckDB connection

    Raises:
        duckdb.Error: If SQL execution fails

    """
    conn.execute(RUNS_TABLE_DDL)


def check_tables(conn: duckdb.DuckDBPyConnection, *, silent: bool = False) -> bool:
    """Check if runs table exists with correct schema.

    Note: As of 2025-11-17, the separate lineage table was removed.
    Lineage is now tracked via parent_run_id column in runs table.

    Args:
        conn: DuckDB connection
        silent: If True, suppress error messages (default: False)

    Returns:
        True if table exists and has correct schema, False otherwise

    """
    # Check if runs table exists
    result = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name = 'runs'
    """).fetchall()

    if not result:
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

    required_runs_columns = set(RUNS_TABLE_SCHEMA.names)

    actual_runs_columns = {col[0] for col in runs_columns}

    if required_runs_columns != actual_runs_columns:
        if not silent:
            missing = required_runs_columns - actual_runs_columns
            extra = actual_runs_columns - required_runs_columns
            print(f"Runs table schema mismatch. Missing: {missing}. Extra: {extra}")
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

    # Connect to DuckDB
    conn = duckdb.connect(str(args.db_path))

    try:
        if args.check:
            # Dry run: check if tables exist
            if check_tables(conn):
                sys.exit(0)
            else:
                sys.exit(2)

        # Check if tables already exist
        if args.force:
            # Force flag: Drop existing tables unconditionally (migration path)
            conn.execute("DROP TABLE IF EXISTS runs")
        elif check_tables(conn, silent=True):
            # Tables exist with correct schema - nothing to do
            sys.exit(0)

        # Create tables
        create_tables(conn)

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
