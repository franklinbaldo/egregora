"""Tests for check_private_imports pre-commit hook."""

import sys
from pathlib import Path

# Add dev_tools to path
sys.path.insert(0, str(Path(__file__).parents[3] / "dev_tools"))

from check_private_imports import (
    check_all_for_private_names,
    check_private_imports,
)


class TestPrivateImportsChecker:
    """Test the pre-commit hook for detecting private import anti-patterns."""

    def test_check_all_for_private_names_detects_violation(self, tmp_path):
        """Test detection of private names exported in __all__."""
        code = """
__all__ = ["public_func", "_private_func"]

def public_func():
    pass

def _private_func():
    pass
"""
        f = tmp_path / "test.py"
        f.write_text(code)
        errors = check_all_for_private_names(f)

        assert len(errors) == 1
        assert "_private_func" in errors[0]
        assert "__all__" in errors[0]

    def test_check_all_for_private_names_allows_public_names(self, tmp_path):
        """Test that public names in __all__ are allowed."""
        code = """
__all__ = ["public_func", "PublicClass"]

def public_func():
    pass

class PublicClass:
    pass
"""
        f = tmp_path / "test.py"
        f.write_text(code)
        errors = check_all_for_private_names(f)

        assert len(errors) == 0

    def test_check_private_imports_detects_violation(self, tmp_path):
        """Test detection of cross-module private function imports."""
        code = """
from other_module import _private_function

def my_function():
    return _private_function()
"""
        f = tmp_path / "test.py"
        f.write_text(code)
        errors = check_private_imports(f)

        assert len(errors) == 1
        assert "_private_function" in errors[0]
        assert "Importing private" in errors[0]

    def test_check_private_imports_allows_public(self, tmp_path):
        """Test that public function imports are allowed."""
        code = """
from other_module import public_function

def my_function():
    return public_function()
"""
        f = tmp_path / "test.py"
        f.write_text(code)
        errors = check_private_imports(f)

        assert len(errors) == 0

    def test_check_private_imports_allows_dunder(self, tmp_path):
        """Test that dunder imports (like __version__) are allowed."""
        code = """
from other_module import __version__

VERSION = __version__
"""
        f = tmp_path / "test.py"
        f.write_text(code)
        errors = check_private_imports(f)

        assert len(errors) == 0

    def test_check_private_imports_flags_ibis_underscore(self, tmp_path):
        """Test that ibis._ import is treated as private."""
        code = """
from ibis import _

t = _.col
"""
        f = tmp_path / "test.py"
        f.write_text(code)
        errors = check_private_imports(f)

        assert len(errors) == 1


class TestRegressionTests:
    """Regression tests for actual violations found in codebase."""

    def test_avatar_import_was_violation(self, tmp_path):
        """Test that the old avatar import pattern would be caught.

        Regression test - the bug we fixed in PR #1036 would have been caught.
        """
        # This was the problematic code pattern
        code = """
from egregora.knowledge.avatar import _generate_fallback_avatar_url

url = _generate_fallback_avatar_url(uuid)
"""
        f = tmp_path / "adapter.py"
        f.write_text(code)
        errors = check_private_imports(f)

        # Should detect this as a violation
        assert len(errors) == 1
        assert "_generate_fallback_avatar_url" in errors[0]
