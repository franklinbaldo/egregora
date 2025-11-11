"""CI-friendly wrapper for pandas import enforcement.

This module provides a simple entry point for CI to check pandas imports.
The actual test logic is in test_banned_imports.py.

Usage:
    # As pytest test
    pytest tests/linting/test_no_pandas_escape.py

    # As standalone script (for CI)
    python tests/linting/test_no_pandas_escape.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add tests directory to path so we can import the test module
tests_dir = Path(__file__).parent.parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

from linting.test_banned_imports import (  # type: ignore[import-not-found]
    check_file_for_banned_imports,
    get_python_files,
)


def main() -> int:
    """Check for pandas imports and exit with error code if found.

    Returns:
        0 if no pandas imports found, 1 if violations detected
    """
    all_errors = []

    try:
        for file_path in get_python_files():
            errors = check_file_for_banned_imports(file_path)
            all_errors.extend(errors)
    except Exception:  # noqa: BLE001 - Test error handler returns exit code
        return 1

    if all_errors:
        for _error in all_errors:
            pass
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
