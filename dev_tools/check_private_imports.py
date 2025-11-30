#!/usr/bin/env python3
"""Pre-commit hook to prevent private function anti-patterns.

Checks:
1. No underscore-prefixed names in __all__
2. No cross-module imports of underscore-prefixed functions
"""

import ast
import sys
from pathlib import Path


def check_all_for_private_names(file_path: Path) -> list[str]:
    """Check if __all__ contains any private (underscore-prefixed) names."""
    errors = []
    try:
        tree = ast.parse(file_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List | ast.Tuple):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    if elt.value.startswith("_"):
                                        errors.append(
                                            f"{file_path}:{elt.lineno}: __all__ contains private name '{elt.value}'"
                                        )
    except SyntaxError:
        pass  # Skip files with syntax errors (will be caught by other tools)
    return errors


def check_private_imports(file_path: Path) -> list[str]:
    """Check for imports of underscore-prefixed names from other modules."""
    errors = []
    # Special cases that are OK
    ALLOWED_PRIVATE_IMPORTS = {
        ("ibis", "_"),  # ibis._ is a conventional placeholder (like SQL's _)
    }

    try:
        tree = ast.parse(file_path.read_text())
        for node in ast.walk(tree):
            # Check: from module import _private
            if isinstance(node, ast.ImportFrom):
                if node.module and not node.module.startswith("."):  # Only check absolute imports
                    for alias in node.names:
                        if alias.name.startswith("_"):
                            # Skip allowed cases
                            if (node.module, alias.name) in ALLOWED_PRIVATE_IMPORTS:
                                continue
                            errors.append(
                                f"{file_path}:{node.lineno}: Importing private name '{alias.name}' "
                                f"from '{node.module}'"
                            )
    except SyntaxError:
        pass  # Skip files with syntax errors
    return errors


def main() -> int:
    """Run checks on all Python files passed as arguments."""
    all_errors = []

    for file_path_str in sys.argv[1:]:
        file_path = Path(file_path_str)
        if file_path.suffix != ".py":
            continue

        # Check 1: Private names in __all__
        all_errors.extend(check_all_for_private_names(file_path))

        # Check 2: Cross-module private imports
        all_errors.extend(check_private_imports(file_path))

    if all_errors:
        for _error in all_errors:
            pass
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
