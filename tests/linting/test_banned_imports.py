"""Enforce Ibis-first architecture - ban pandas imports in application code.

This test ensures that pandas is not imported in src/egregora/, enforcing
the "Ibis + DuckDB" design principle. See CLAUDE.md for policy details.

Rationale:
- pandas adds memory overhead and dependency complexity
- Ibis + DuckDB provide all necessary DataFrame operations
- PyArrow may be used internally by DuckDB, but should not be imported directly
  in application code (except for type hints in TYPE_CHECKING blocks)

Exceptions:
- src/egregora/compat/: Legacy compatibility shims (if needed)
- src/egregora/testing/: Test utilities may import pandas for fixture creation
- TYPE_CHECKING blocks: Allowed for type hints only
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# Directories where pandas imports are allowed
WHITELIST_PATHS = re.compile(r"(src/egregora/compat/|src/egregora/testing/)")


def get_python_files() -> list[Path]:
    """Get all Python files in src/egregora/."""
    src_dir = Path("src/egregora")
    if not src_dir.exists():
        pytest.skip("src/egregora directory not found")

    return list(src_dir.rglob("*.py"))


def is_in_type_checking_block(node: ast.Import | ast.ImportFrom, tree: ast.Module) -> bool:
    """Check if import is inside a TYPE_CHECKING block."""
    for top_level in ast.walk(tree):
        if isinstance(top_level, ast.If):
            # Check if this is `if TYPE_CHECKING:`
            if isinstance(top_level.test, ast.Name) and top_level.test.id == "TYPE_CHECKING":
                # Check if our import node is in this if block
                for stmt in ast.walk(top_level):
                    if stmt is node:
                        return True
    return False


def check_file_for_banned_imports(file_path: Path) -> list[str]:
    """Check a Python file for banned pandas imports.

    Returns:
        List of error messages (empty if no issues found)

    """
    # Skip whitelisted paths
    if WHITELIST_PATHS.search(str(file_path)):
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        # Skip files that can't be parsed
        return []

    errors = []

    for node in ast.walk(tree):
        banned_module = None

        # Check `import pandas` or `import pandas as pd`
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pandas" or alias.name.startswith("pandas."):
                    if not is_in_type_checking_block(node, tree):
                        banned_module = alias.name
                        break

        # Check `from pandas import ...`
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "pandas" or node.module.startswith("pandas.")):
                if not is_in_type_checking_block(node, tree):
                    banned_module = node.module

        if banned_module:
            errors.append(
                f"{file_path}:{node.lineno}: Banned import 'pandas' found. "
                f"Use Ibis + DuckDB instead. See CLAUDE.md for Ibis-first policy."
            )

    return errors


def test_no_pandas_imports_in_src():
    """Enforce that pandas is not imported in src/egregora/ (except whitelisted paths)."""
    all_errors = []

    for file_path in get_python_files():
        errors = check_file_for_banned_imports(file_path)
        all_errors.extend(errors)

    if all_errors:
        error_msg = "\n❌ Found banned pandas imports:\n\n" + "\n".join(all_errors)
        error_msg += "\n\n📖 Policy: Egregora uses Ibis + DuckDB for all DataFrame operations."
        error_msg += "\n   See CLAUDE.md section 'Ibis-First Coding Standard' for details."
        pytest.fail(error_msg)


def test_whitelisted_paths_work():
    """Verify that whitelisted paths would be skipped (if they existed)."""
    test_paths = [
        Path("src/egregora/compat/legacy.py"),
        Path("src/egregora/testing/fixtures.py"),
    ]

    for path in test_paths:
        assert WHITELIST_PATHS.search(str(path)), f"Whitelist should match {path}"
