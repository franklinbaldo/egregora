#!/usr/bin/env python3
"""Pre-commit hook to prevent direct config instantiation in tests.

Checks for:
- Direct EgregoraConfig() calls without fixtures
- Direct Settings class instantiation
- Hardcoded infrastructure paths
"""

import re
import sys
from pathlib import Path

VIOLATIONS = [
    (
        r"\bEgregoraConfig\(\)",
        "Use test_config, minimal_config, or config_factory fixture instead of EgregoraConfig()",
    ),
    (
        r"\bRAGSettings\(\)",
        "Use test_rag_settings or rag_settings_factory fixture instead of RAGSettings()",
    ),
    (
        r"\bModelSettings\(\)",
        "Use test_model_settings fixture instead of ModelSettings()",
    ),
    (
        r'Path\((["\\])\.egregora/',
        "Use tmp_path fixture instead of hardcoded .egregora/ paths",
    ),
]


def check_file(file_path: Path) -> list[str]:
    """Check a single file for violations."""
    errors = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return []

    for pattern, message in VIOLATIONS:
        # Avoid checking if content looks like binary or empty
        if not content:
            continue

        try:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Get line number
                line_num = content[: match.start()].count("\n") + 1
                errors.append(f"{file_path}:{line_num}: {message}")
        except re.error as e:
            # Fail on invalid regex matches
            print(f"Error: Regex error in {file_path}: {e}")
            # Raise exception to be caught in main or just treat as error?
            # Better to append to errors so it fails the check
            errors.append(f"{file_path}:0: Regex error: {e}")

    return errors


def main() -> int:
    """Runs the pre-commit hook to check all test files for violations."""
    # Force UTF-8 for stdout/stderr to avoid UnicodeEncodeError on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    test_files = Path("tests").rglob("test_*.py")
    all_errors = []

    for file_path in test_files:
        # Skip conftest.py (defines fixtures) and utils (test infrastructure)
        if file_path.name == "conftest.py" or "utils" in file_path.parts:
            continue

        errors = check_file(file_path)
        all_errors.extend(errors)

    if all_errors:
        for error in all_errors:
            sys.stderr.write(f"{error}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
