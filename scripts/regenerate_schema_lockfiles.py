#!/usr/bin/env python
"""Regenerate schema lockfiles from IR_MESSAGE_SCHEMA (single source of truth).

This script generates the SQL and JSON lockfiles from the Python schema definition.
The Python schema (IR_MESSAGE_SCHEMA in validation.py) is the single source of truth.

Usage:
    python scripts/regenerate_schema_lockfiles.py

"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from egregora.database.validation import generate_ir_lockfile_json, generate_ir_sql_ddl


def main() -> None:
    """Regenerate schema lockfiles."""
    schema_dir = Path(__file__).parent.parent / "schema"
    schema_dir.mkdir(exist_ok=True)

    print("Regenerating schema lockfiles from IR_MESSAGE_SCHEMA...")

    # Generate SQL lockfile
    sql_lockfile = schema_dir / "ir_v1.sql"
    sql_content = generate_ir_sql_ddl()
    sql_lockfile.write_text(sql_content)
    print(f"✓ Generated {sql_lockfile}")

    # Generate JSON lockfile
    json_lockfile = schema_dir / "ir_v1.json"
    json_content = json.dumps(generate_ir_lockfile_json(), indent=2)
    json_lockfile.write_text(json_content + "\n")  # Add trailing newline
    print(f"✓ Generated {json_lockfile}")

    print("\nLockfiles regenerated successfully!")
    print("Note: These files are for validation/documentation only.")
    print("The runtime SQL is generated dynamically from IR_MESSAGE_SCHEMA.")


if __name__ == "__main__":
    main()
