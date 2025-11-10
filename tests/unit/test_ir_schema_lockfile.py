"""Tests for IR schema lockfile validation.

Ensures the schema lockfile (schema/ir_v1.json) stays in sync with code
(src/egregora/database/validation.py:IR_V1_SCHEMA).
"""

import json
import subprocess
from pathlib import Path

from egregora.database.validation import IR_V1_SCHEMA


def test_ir_schema_lockfile_exists():
    """IR v1 schema lockfile must exist."""
    lockfile = Path("schema/ir_v1.json")
    assert lockfile.exists(), "schema/ir_v1.json lockfile missing"


def test_ir_schema_lockfile_valid_json():
    """IR v1 schema lockfile must be valid JSON."""
    lockfile = Path("schema/ir_v1.json")
    with open(lockfile) as f:
        data = json.load(f)

    assert "columns" in data
    assert "version" in data
    assert isinstance(data["columns"], dict)


def test_ir_schema_matches_lockfile():
    """IR_V1_SCHEMA in code must match lockfile."""
    lockfile = Path("schema/ir_v1.json")
    with open(lockfile) as f:
        lockfile_data = json.load(f)

    # Check column count
    lockfile_columns = set(lockfile_data["columns"].keys())
    code_columns = set(IR_V1_SCHEMA.names)

    assert lockfile_columns == code_columns, (
        f"Column mismatch. Lockfile: {lockfile_columns}, Code: {code_columns}"
    )

    # Check each column exists in both
    for col_name in lockfile_columns:
        assert col_name in IR_V1_SCHEMA.names, f"Column '{col_name}' in lockfile but not in code schema"


def test_check_ir_schema_script_passes():
    """The check_ir_schema.py CI script must pass."""
    result = subprocess.run(
        ["python", "scripts/check_ir_schema.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Schema validation failed:\n{result.stdout}\n{result.stderr}"


def test_ir_schema_sql_lockfile_exists():
    """IR v1 SQL schema lockfile must exist."""
    lockfile = Path("schema/ir_v1.sql")
    assert lockfile.exists(), "schema/ir_v1.sql lockfile missing"

    # Verify it contains CREATE TABLE
    content = lockfile.read_text()
    assert "CREATE TABLE" in content
    assert "ir_messages" in content
