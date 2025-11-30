"""Tests for check_private_imports pre-commit hook."""

import ast

# Import the check_private_imports module
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "dev_tools"))

from check_private_imports import (
    check_cross_module_private_imports,
    check_file,
    check_private_in_all,
)


class TestPrivateImportsChecker:
    """Test the pre-commit hook for detecting private import anti-patterns."""

    def test_check_private_in_all_detects_violation(self):
        """Test detection of private names exported in __all__."""
        code = """
__all__ = ["public_func", "_private_func"]

def public_func():
    pass

def _private_func():
    pass
"""
        tree = ast.parse(code)
        errors = check_private_in_all(tree, "test.py")

        assert len(errors) == 1
        assert "_private_func" in errors[0]
        assert "__all__" in errors[0]

    def test_check_private_in_all_allows_public_names(self):
        """Test that public names in __all__ are allowed."""
        code = """
__all__ = ["public_func", "PublicClass"]

def public_func():
    pass

class PublicClass:
    pass
"""
        tree = ast.parse(code)
        errors = check_private_in_all(tree, "test.py")

        assert len(errors) == 0

    def test_check_cross_module_imports_detects_violation(self):
        """Test detection of cross-module private function imports."""
        code = """
from other_module import _private_function

def my_function():
    return _private_function()
"""
        tree = ast.parse(code)
        errors = check_cross_module_private_imports(tree, "test.py")

        assert len(errors) == 1
        assert "_private_function" in errors[0]
        assert "Importing private" in errors[0]

    def test_check_cross_module_imports_allows_public(self):
        """Test that public function imports are allowed."""
        code = """
from other_module import public_function

def my_function():
    return public_function()
"""
        tree = ast.parse(code)
        errors = check_cross_module_private_imports(tree, "test.py")

        assert len(errors) == 0

    def test_check_cross_module_imports_allows_dunder(self):
        """Test that dunder imports (like __version__) are allowed."""
        code = """
from other_module import __version__

VERSION = __version__
"""
        tree = ast.parse(code)
        errors = check_cross_module_private_imports(tree, "test.py")

        assert len(errors) == 0

    def test_check_file_combines_all_checks(self):
        """Test that check_file runs all validation checks."""
        code = """
__all__ = ["_bad_export"]

from other import _private_func

def _bad_export():
    return _private_func()
"""
        errors = check_file("test.py", code)

        # Should find both violations
        assert len(errors) == 2
        # One for __all__, one for import
        assert any("__all__" in e for e in errors)
        assert any("Importing private" in e for e in errors)

    def test_check_file_accepts_clean_code(self):
        """Test that check_file accepts code with no violations."""
        code = '''
__all__ = ["public_api"]

from other import public_function

def public_api():
    return public_function()

def _internal_helper():
    """Private helper, not exported."""
    pass
'''
        errors = check_file("test.py", code)

        assert len(errors) == 0


class TestRegressionTests:
    """Regression tests for actual violations found in codebase."""

    def test_avatar_import_was_violation(self):
        """Test that the old avatar import pattern would be caught.

        Regression test - the bug we fixed in PR #1036 would have been caught.
        """
        # This was the problematic code pattern
        code = """
from egregora.knowledge.avatar import _generate_fallback_avatar_url

url = _generate_fallback_avatar_url(uuid)
"""
        tree = ast.parse(code)
        errors = check_cross_module_private_imports(tree, "adapter.py")

        # Should detect this as a violation
        assert len(errors) == 1
        assert "_generate_fallback_avatar_url" in errors[0]
