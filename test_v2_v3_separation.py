#!/usr/bin/env python3
"""Test to enforce V2/V3 separation.

This test ensures that:
1. V2 (egregora/) never imports from V3 (egregora_v3/)
2. V3 (egregora_v3/) minimally imports from V2 (only allowed exceptions)
3. Both codebases remain independent
"""

import ast
import sys
from pathlib import Path
from typing import Set, List, Tuple


# Allowed V3 → V2 imports (temporary legacy dependencies)
ALLOWED_V3_TO_V2_IMPORTS = {
    # Banner generation temporarily uses V2 components
    # These will be migrated to V3-native implementations
    "egregora_v3/engine/banner/feed_generator.py": {
        "egregora.data_primitives.document",
        "egregora.agents.banner.agent",
        "egregora.agents.banner.image_generation",
    },
    "egregora_v3/engine/banner/generator.py": {
        "egregora.data_primitives.document",
        "egregora.resources.prompts",
        "egregora.agents.banner.image_generation",
    },
}


def find_python_files(directory: Path) -> List[Path]:
    """Find all Python files in directory."""
    return list(directory.rglob("*.py"))


def get_imports_from_file(file_path: Path) -> Set[str]:
    """Extract all import statements from a Python file (full module names)."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))
        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)  # Keep full module name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)  # Keep full module name

        return imports
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"⚠️  Warning: Could not parse {file_path}: {e}")
        return set()


def check_v2_to_v3_imports() -> List[Tuple[Path, Set[str]]]:
    """Check if V2 imports from V3 (NOT ALLOWED)."""
    violations = []
    v2_root = Path("src/egregora")

    if not v2_root.exists():
        return violations

    for py_file in find_python_files(v2_root):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file) or "test_" in py_file.name:
            continue

        imports = get_imports_from_file(py_file)
        v3_imports = {imp for imp in imports if imp == "egregora_v3" or imp.startswith("egregora_v3.")}

        if v3_imports:
            violations.append((py_file, v3_imports))

    return violations


def check_v3_to_v2_imports() -> List[Tuple[Path, Set[str]]]:
    """Check if V3 imports from V2 (RESTRICTED - only allowed exceptions)."""
    violations = []
    v3_root = Path("src/egregora_v3")

    if not v3_root.exists():
        return violations

    for py_file in find_python_files(v3_root):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file) or "test_" in py_file.name:
            continue

        # Get relative path for checking allowed imports
        rel_path = str(py_file.relative_to(Path("src")))

        imports = get_imports_from_file(py_file)

        # Find V2 imports (egregora but not egregora_v3)
        v2_imports = set()
        for imp in imports:
            if imp == "egregora" or (imp.startswith("egregora.") and not imp.startswith("egregora_v3.")):
                v2_imports.add(imp)

        if v2_imports:
            # Check if these imports are allowed
            allowed = ALLOWED_V3_TO_V2_IMPORTS.get(rel_path, set())

            # Filter to only violations (imports not in allowed list)
            # Match exact module or submodule (e.g., "egregora.agents" matches "egregora.agents.banner")
            violations_for_file = set()
            for imp in v2_imports:
                is_allowed = False
                for allowed_prefix in allowed:
                    # Match if import equals allowed or is a submodule of allowed
                    if imp == allowed_prefix or imp.startswith(allowed_prefix + "."):
                        is_allowed = True
                        break
                if not is_allowed:
                    violations_for_file.add(imp)

            if violations_for_file:
                violations.append((py_file, violations_for_file))

    return violations


def test_v2_v3_separation():
    """Main test function."""
    print("=" * 70)
    print("V2/V3 SEPARATION TEST")
    print("=" * 70)
    print()

    all_passed = True

    # Test 1: V2 must NOT import from V3
    print("Test 1: V2 (egregora/) must NOT import from V3 (egregora_v3/)")
    print("-" * 70)
    v2_to_v3 = check_v2_to_v3_imports()

    if v2_to_v3:
        all_passed = False
        print("❌ FAILED: V2 imports from V3 detected!")
        for file_path, imports in v2_to_v3:
            print(f"  {file_path}:")
            for imp in imports:
                print(f"    - {imp}")
    else:
        print("✅ PASSED: V2 does not import from V3")
    print()

    # Test 2: V3 should minimize imports from V2
    print("Test 2: V3 (egregora_v3/) should minimize imports from V2 (egregora/)")
    print("-" * 70)
    v3_to_v2 = check_v3_to_v2_imports()

    if v3_to_v2:
        all_passed = False
        print("❌ FAILED: Unexpected V3 → V2 imports detected!")
        print("   (Only allowed exceptions should exist)")
        for file_path, imports in v3_to_v2:
            print(f"  {file_path}:")
            for imp in imports:
                print(f"    - {imp}")
        print()
        print("  If these imports are intentional, add them to ALLOWED_V3_TO_V2_IMPORTS")
    else:
        print("✅ PASSED: V3 only has allowed imports from V2")
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    # Count allowed V3 → V2 imports
    total_allowed = sum(len(imports) for imports in ALLOWED_V3_TO_V2_IMPORTS.values())

    print(f"V2 → V3 violations: {len(v2_to_v3)} (must be 0)")
    print(f"V3 → V2 violations: {len(v3_to_v2)} (must be 0)")
    print(f"V3 → V2 allowed exceptions: {total_allowed} imports")
    print()

    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("V2 and V3 are properly separated!")
        return 0
    else:
        print("❌ TESTS FAILED")
        print("V2/V3 separation violated - fix imports above")
        return 1


if __name__ == "__main__":
    sys.exit(test_v2_v3_separation())
