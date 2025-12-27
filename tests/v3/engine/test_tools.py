"""Tests for egregora_v3.engine.tools."""

from egregora_v3.engine.tools import TOOLS


def test_search_prior_work_is_not_in_tools_list():
    """Confirms that the placeholder tool is no longer in the TOOLS list."""
    # This test asserts the successful removal of the dead code.
    assert "search_prior_work" not in [
        func.__name__ for func in TOOLS
    ], "search_prior_work should not be in the TOOLS list after refactoring"
