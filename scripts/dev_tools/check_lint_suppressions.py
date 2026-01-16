#!/usr/bin/env python3
"""Check for lint suppression comments (noqa, type: ignore, etc.).

This pre-commit hook enforces that all code follows linting rules without
suppression comments. Exceptions must be explicitly allowed.
"""

import re
import sys
from pathlib import Path

# Patterns to detect
SUPPRESSION_PATTERNS = [
    r"#\s*noqa",  # Ruff/flake8 suppressions
    r"#\s*type:\s*ignore",  # mypy suppressions
    r"#\s*pylint:\s*disable",  # pylint suppressions
    r"#\s*pyright:\s*ignore",  # pyright suppressions
]

# NO files are allowed to have suppressions!
# Use pyproject.toml [tool.ruff.lint.per-file-ignores] instead.
ALLOWED_FILES: set[str] = set()

# Only exclude generated/external code
ALLOWED_PATTERNS = [
    r"^\.jules/",  # Jules code is excluded from our linting
    r"^artifacts/",  # Generated artifacts
]


def should_skip_file(file_path: str) -> bool:
    """Check if file should be skipped from suppression checking."""
    if file_path in ALLOWED_FILES:
        return True
    return any(re.match(pattern, file_path) for pattern in ALLOWED_PATTERNS)


def check_file(file_path: Path) -> list[tuple[int, str]]:
    """Check a file for lint suppression comments.

    Returns:
        List of (line_number, line_content) tuples for violations.
    """
    if should_skip_file(str(file_path)):
        return []

    violations = []
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            for pattern in SUPPRESSION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append((idx, line.strip()))
                    break

    except (UnicodeDecodeError, FileNotFoundError):
        # Skip non-text files or missing files
        pass

    return violations


def main(file_paths: list[str]) -> int:
    """Check all provided files for lint suppressions.

    Returns:
        0 if no violations, 1 if violations found.
    """
    all_violations: dict[str, list[tuple[int, str]]] = {}

    for file_path_str in file_paths:
        file_path = Path(file_path_str)
        if file_path.suffix != ".py":
            continue

        violations = check_file(file_path)
        if violations:
            all_violations[file_path_str] = violations

    if all_violations:
        print("❌ Lint suppression comments found:")
        print()
        for file_path, violations in sorted(all_violations.items()):
            print(f"  {file_path}:")
            for line_num, line_content in violations:
                print(f"    Line {line_num}: {line_content}")
            print()

        print("💡 Instead of suppressing warnings:")
        print("  1. Fix the underlying issue")
        print("  2. If the rule is wrong, disable it globally in pyproject.toml")
        print("  3. If absolutely necessary, add the file to ALLOWED_FILES")
        print()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
