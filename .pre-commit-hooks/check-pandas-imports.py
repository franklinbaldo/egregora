#!/usr/bin/env python3
"""Check for banned pandas imports in src/egregora (Ibis-first policy).

Allows pandas imports only in:
- TYPE_CHECKING blocks (for type hints)
- /compat/ directories
- /testing/ directories
"""

import re
import sys
from pathlib import Path


def is_in_type_checking_block(lines: list[str], line_num: int) -> bool:
    """Check if a line is inside a TYPE_CHECKING block."""
    # Look backwards from the import line to find if we're in a TYPE_CHECKING block
    indent_of_import = len(lines[line_num]) - len(lines[line_num].lstrip())

    for i in range(line_num - 1, -1, -1):
        line = lines[i]
        stripped = line.strip()

        # Empty lines or comments don't break the block
        if not stripped or stripped.startswith("#"):
            continue

        current_indent = len(line) - len(line.lstrip())

        # If we're at the same or less indentation, check if it's TYPE_CHECKING
        if current_indent < indent_of_import:
            if "TYPE_CHECKING" in line:
                return True
            # We've exited the block
            return False

    return False


def check_file(file_path: Path) -> list[str]:
    """Check a single file for banned pandas imports.

    Returns list of error messages.
    """
    errors = []

    try:
        content = file_path.read_text()
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Skip if in /compat/ or /testing/ directory
            if "/compat/" in str(file_path) or "/testing/" in str(file_path):
                continue

            # Check for pandas imports
            if re.search(r"^\s*(from|import)\s+pandas\b", line):
                # Allow if in TYPE_CHECKING block
                if is_in_type_checking_block(lines, i):
                    continue

                errors.append(f"{file_path}:{i + 1}: {line.strip()}")

    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return errors


def main() -> int:
    """Main entry point."""
    src_dir = Path("src/egregora")

    if not src_dir.exists():
        print(f"Error: {src_dir} does not exist", file=sys.stderr)
        return 1

    all_errors = []

    # Find all Python files in src/egregora
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        errors = check_file(py_file)
        all_errors.extend(errors)

    if all_errors:
        print("❌ Found banned pandas imports. Use Ibis + DuckDB instead.")
        print("   TYPE_CHECKING imports are allowed for type hints.")
        print("   See docs/development/agents/claude.md for Ibis-first policy.\n")
        for error in all_errors:
            print(f"   {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
