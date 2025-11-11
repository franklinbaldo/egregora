#!/usr/bin/env python3
"""CI check to verify IR v1 schema hasn't drifted from lockfile.

This script compares the canonical IR v1 schema lockfile (schema/ir_v1.json)
against the actual schema defined in code (src/egregora/database/validation.py).

Exits with code 1 if schemas don't match, preventing accidental schema changes
from being committed without updating the lockfile.

Usage:
    python scripts/check_ir_schema.py

Exit codes:
    0: Schemas match
    1: Schema drift detected
    2: Error loading schemas
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import ibis.expr.datatypes as dt


def load_lockfile_schema(lockfile_path: Path) -> dict:
    """Load schema from JSON lockfile."""
    try:
        with open(lockfile_path) as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(2)
    except json.JSONDecodeError:
        sys.exit(2)


def load_code_schema():
    """Load IR_V1_SCHEMA from code."""
    try:
        # Add src to path to import egregora
        src_path = Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))

        from egregora.database.validation import IR_V1_SCHEMA

        return IR_V1_SCHEMA
    except ImportError:
        sys.exit(2)


def dtype_to_string(dtype: dt.DataType) -> str:
    """Convert Ibis dtype to string representation for comparison."""
    if isinstance(dtype, dt.UUID):
        return "UUID"
    if isinstance(dtype, dt.String):
        return "String"
    if isinstance(dtype, dt.Timestamp):
        return "Timestamp"
    if isinstance(dtype, dt.JSON):
        return "JSON"
    if isinstance(dtype, dt.Int64):
        return "Int64"
    if isinstance(dtype, dt.Boolean):
        return "Boolean"
    return str(dtype)


def compare_schemas(lockfile_data: dict, code_schema) -> list[str]:
    """Compare lockfile schema with code schema.

    Returns:
        List of differences (empty if schemas match)

    """
    differences = []

    # Check column count
    lockfile_columns = set(lockfile_data["columns"].keys())
    code_columns = set(code_schema.names)

    if lockfile_columns != code_columns:
        missing_in_lockfile = code_columns - lockfile_columns
        extra_in_lockfile = lockfile_columns - code_columns

        if missing_in_lockfile:
            differences.append(f"Missing in lockfile: {', '.join(missing_in_lockfile)}")
        if extra_in_lockfile:
            differences.append(f"Extra in lockfile: {', '.join(extra_in_lockfile)}")

        return differences

    # Check each column's type and nullability
    for col_name in lockfile_columns:
        lockfile_col = lockfile_data["columns"][col_name]
        code_dtype = code_schema[col_name]

        # Check type
        lockfile_type = lockfile_col["type"]
        code_type = dtype_to_string(code_dtype)

        if lockfile_type != code_type:
            differences.append(
                f"Column '{col_name}' type mismatch: "
                f"lockfile={lockfile_type}, code={code_type}"
            )

        # Check nullability
        lockfile_nullable = lockfile_col["nullable"]
        code_nullable = code_dtype.nullable

        if lockfile_nullable != code_nullable:
            differences.append(
                f"Column '{col_name}' nullability mismatch: "
                f"lockfile={lockfile_nullable}, code={code_nullable}"
            )

    return differences


def main() -> int:
    """Run schema validation check."""
    # Resolve paths
    repo_root = Path(__file__).parent.parent
    lockfile_path = repo_root / "schema" / "ir_v1.json"

    # Load schemas
    lockfile_data = load_lockfile_schema(lockfile_path)

    code_schema = load_code_schema()

    # Compare
    differences = compare_schemas(lockfile_data, code_schema)

    if not differences:
        return 0

    for _diff in differences:
        pass


    return 1


if __name__ == "__main__":
    sys.exit(main())
