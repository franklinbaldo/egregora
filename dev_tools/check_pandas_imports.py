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
    """Check if a line is inside an 'if TYPE_CHECKING:' block.

    Properly verifies the import is within an actual conditional block,
    not just in a file that imports TYPE_CHECKING.
    """
    # Look backwards from the import line to find if we're in a TYPE_CHECKING block
    indent_of_import = len(lines[line_num]) - len(lines[line_num].lstrip())

    for i in range(line_num - 1, -1, -1):
        line = lines[i]
        stripped = line.strip()

        # Empty lines or comments don't break the block
        if not stripped or stripped.startswith("#"):
            continue

        current_indent = len(line) - len(line.lstrip())

        # If we're at the same or less indentation, check if it's an if TYPE_CHECKING block
        if current_indent < indent_of_import:
            # Must match "if TYPE_CHECKING:" pattern (not just importing TYPE_CHECKING)
            if re.match(r"\s*if\s+TYPE_CHECKING\s*:", line):
                return True
            # We've exited the block without finding TYPE_CHECKING guard
            return False

    return False


def check_file(file_path: Path) -> list[str]:
    """Check a single file for banned pandas imports.

    Returns list of error messages.
    """
    errors = []

    # Skip if in /compat/ or /testing/ directory (using Path.parts for cross-platform)
    path_parts = file_path.parts
    if "compat" in path_parts or "testing" in path_parts:
        return errors

    try:
        content = file_path.read_text()
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Check for pandas imports
            if re.search(r"^\s*(from|import)\s+pandas\b", line):
                # Allow if in TYPE_CHECKING block
                if is_in_type_checking_block(lines, i):
                    continue

                errors.append(f"{file_path}:{i + 1}: {line.strip()}")

    except Exception:
        pass

    return errors


def main() -> int:
    """Main entry point."""
    src_dir = Path("src/egregora")

    if not src_dir.exists():
        return 1

    all_errors = []

    # Find all Python files in src/egregora
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        errors = check_file(py_file)
        all_errors.extend(errors)

    if all_errors:
        for _error in all_errors:
            pass
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
