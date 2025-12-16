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
        r'Path\(["\']\.egregora/',
        "Use tmp_path fixture instead of hardcoded .egregora/ paths",
    ),
]


def check_file(file_path: Path) -> list[str]:
    """Check a single file for violations."""
    errors = []
    content = file_path.read_text()

    for pattern, message in VIOLATIONS:
        matches = re.finditer(pattern, content)
        for match in matches:
            # Get line number
            line_num = content[: match.start()].count("\n") + 1
            errors.append(f"{file_path}:{line_num}: {message}")

    return errors


def main() -> int:
    test_files = Path("tests").rglob("test_*.py")
    all_errors = []

    for file_path in test_files:
        # Skip conftest.py (defines fixtures) and utils (test infrastructure)
        if file_path.name == "conftest.py" or "utils" in file_path.parts:
            continue
        if ("tests" in file_path.parts) and ("v3" in file_path.parts):
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
