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
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
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
    except Exception:
        pass  # Skip files that can't be read or parsed
    return errors


def check_private_imports(file_path: Path) -> list[str]:
    """Check for imports of underscore-prefixed names from other modules."""
    errors = []
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # Check: from module import _private
            if isinstance(node, ast.ImportFrom):
                if node.module and not node.module.startswith("."):  # Only check absolute imports
                    errors.extend(
                        f"{file_path}:{node.lineno}: Importing private name '{alias.name}' "
                        f"from '{node.module}'"
                        for alias in node.names
                        if alias.name.startswith("_")
                        and not (alias.name.startswith("__") and alias.name.endswith("__"))
                    )
    except SyntaxError:
        pass  # Skip files with syntax errors
    except Exception:
        pass
    return errors


def main() -> int:
    """Run checks on all Python files passed as arguments."""
    all_errors = []

    for file_path_str in sys.argv[1:]:
        file_path = Path(file_path_str)
        if file_path.suffix != ".py":
            continue
        if "tests" in file_path.parts:
            continue

        # Check 1: Private names in __all__
        all_errors.extend(check_all_for_private_names(file_path))

        # Check 2: Cross-module private imports
        all_errors.extend(check_private_imports(file_path))

    if all_errors:
        for error in all_errors:
            sys.stderr.write(f"{error}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
