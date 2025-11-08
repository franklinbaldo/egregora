#!/usr/bin/env python3
"""Check IR v1 schema drift.

This script validates that the current CONVERSATION_SCHEMA in the codebase
matches the locked IR v1 schema definition in schema/ir_v1.json.

Usage:
    python scripts/check_ir_schema.py           # Check for drift
    python scripts/check_ir_schema.py --update  # Update lockfile (requires approval)
    python scripts/check_ir_schema.py --show    # Show current schema

Exit Codes:
    0: No drift detected
    1: Drift detected or validation error
    2: Lockfile missing
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import ibis

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from egregora.database.schema import CONVERSATION_SCHEMA  # noqa: E402


def load_lockfile(lockfile_path: Path) -> dict[str, Any]:
    """Load IR v1 lockfile."""
    if not lockfile_path.exists():
        print(f"❌ Lockfile not found: {lockfile_path}", file=sys.stderr)
        print("   Create it with: python scripts/check_ir_schema.py --update", file=sys.stderr)
        sys.exit(2)

    with open(lockfile_path) as f:
        return json.load(f)


def ibis_schema_to_dict(schema: ibis.Schema) -> dict[str, str]:
    """Convert Ibis schema to dict for comparison.

    Args:
        schema: Ibis schema object

    Returns:
        Dict mapping field names to type strings
    """
    return {name: str(dtype) for name, dtype in schema.items()}


def normalize_type(type_str: str) -> str:
    """Normalize type strings for comparison.

    Handles variations like:
    - timestamp(timezone='UTC', scale=9) → timestamp(timezone='UTC')
    - string → string
    - !string → string (nullable marker)
    """
    # Remove nullable marker
    type_str = type_str.lstrip("!")

    # Normalize timestamp types (ignore scale)
    if type_str.startswith("timestamp"):
        if "timezone='UTC'" in type_str or 'timezone="UTC"' in type_str:
            return "timestamp(timezone='UTC')"
        return "timestamp"

    # Normalize string/text types
    if type_str in ("string", "text", "String", "Text"):
        return "string"

    # Normalize date types
    if type_str in ("date", "Date"):
        return "date"

    # Normalize UUID types
    if type_str in ("uuid", "UUID"):
        return "uuid"

    # Normalize JSON types
    if type_str in ("json", "JSON"):
        return "json"

    # Normalize integer types
    if type_str in ("int64", "int32", "integer"):
        return "int64"

    return type_str.lower()


def compare_schemas(current: dict[str, str], locked: dict[str, str]) -> tuple[bool, list[str]]:
    """Compare current schema with locked schema.

    Args:
        current: Current schema from codebase
        locked: Locked schema from ir_v1.json

    Returns:
        (is_match, differences)
    """
    differences = []

    # Normalize both schemas
    current_normalized = {k: normalize_type(v) for k, v in current.items()}
    locked_normalized = {k: normalize_type(v) for k, v in locked.items()}

    # Check for added fields
    added = set(current_normalized.keys()) - set(locked_normalized.keys())
    if added:
        differences.append(f"➕ Added fields: {', '.join(sorted(added))}")

    # Check for removed fields
    removed = set(locked_normalized.keys()) - set(current_normalized.keys())
    if removed:
        differences.append(f"➖ Removed fields: {', '.join(sorted(removed))}")

    # Check for type changes
    for field in set(current_normalized.keys()) & set(locked_normalized.keys()):
        current_type = current_normalized[field]
        locked_type = locked_normalized[field]

        if current_type != locked_type:
            differences.append(f"🔄 Type change: {field}: {locked_type} → {current_type}")

    return len(differences) == 0, differences


def show_schema(schema: ibis.Schema) -> None:
    """Pretty-print schema."""
    print("\n📋 Current CONVERSATION_SCHEMA:")
    print("=" * 60)

    schema_dict = ibis_schema_to_dict(schema)
    max_field_len = max(len(name) for name in schema_dict.keys())

    for name, dtype in sorted(schema_dict.items()):
        print(f"  {name:<{max_field_len}}  {dtype}")

    print("=" * 60)
    print(f"Total fields: {len(schema_dict)}\n")


def update_lockfile(lockfile_path: Path, schema: ibis.Schema) -> None:
    """Update lockfile with current schema.

    ⚠️  WARNING: This modifies the locked schema!
    Only use this when intentionally updating the IR v1 contract.
    """
    print("\n⚠️  WARNING: Updating locked IR v1 schema")
    print("=" * 60)

    response = input("Are you sure you want to update the lockfile? (yes/no): ")
    if response.lower() != "yes":
        print("❌ Update cancelled")
        sys.exit(1)

    # Load existing lockfile to preserve metadata
    if lockfile_path.exists():
        with open(lockfile_path) as f:
            lockfile = json.load(f)
    else:
        lockfile = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "IR v1 Schema (Ibis Format)",
            "description": "Auto-generated from CONVERSATION_SCHEMA",
            "version": "1.0.0",
            "locked": True,
        }

    # Update ibis_schema section
    lockfile["ibis_schema"] = ibis_schema_to_dict(schema)

    # Write back
    with open(lockfile_path, "w") as f:
        json.dump(lockfile, f, indent=2)
        f.write("\n")  # Trailing newline

    print(f"✅ Updated: {lockfile_path}")
    print("\n⚠️  Next steps:")
    print("   1. Review changes: git diff schema/ir_v1.json")
    print("   2. Update schema/ir_v1.sql if needed")
    print("   3. Document migration path in CHANGELOG.md")
    print("   4. Bump version if breaking change")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Check IR v1 schema drift")
    parser.add_argument("--update", action="store_true", help="Update lockfile with current schema")
    parser.add_argument("--show", action="store_true", help="Show current schema")
    args = parser.parse_args()

    lockfile_path = PROJECT_ROOT / "schema" / "ir_v1.json"

    # Show schema and exit
    if args.show:
        show_schema(CONVERSATION_SCHEMA)
        sys.exit(0)

    # Update lockfile
    if args.update:
        update_lockfile(lockfile_path, CONVERSATION_SCHEMA)
        sys.exit(0)

    # Check for drift
    print("🔍 Checking IR v1 schema drift...")
    print(f"   Lockfile: {lockfile_path}")
    print(f"   Current: src/egregora/database/schema.py::CONVERSATION_SCHEMA\n")

    lockfile = load_lockfile(lockfile_path)
    locked_schema = lockfile.get("ibis_schema", {})

    current_schema = ibis_schema_to_dict(CONVERSATION_SCHEMA)

    is_match, differences = compare_schemas(current_schema, locked_schema)

    if is_match:
        print("✅ No schema drift detected")
        print(f"   Fields: {len(current_schema)}")
        sys.exit(0)

    # Drift detected
    print("❌ Schema drift detected!")
    print("=" * 60)
    for diff in differences:
        print(f"   {diff}")
    print("=" * 60)

    print("\n⚠️  Schema changes detected. This is a breaking change!")
    print("\nOptions:")
    print("   1. Revert code changes to match lockfile")
    print("   2. Update lockfile: python scripts/check_ir_schema.py --update")
    print("      (Requires version bump + migration path)")
    print("\nSee: docs/architecture/ir-v1-spec.md for migration guidelines")

    sys.exit(1)


if __name__ == "__main__":
    main()
