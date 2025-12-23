"""Tests for vulture_whitelist.py."""

import vulture_whitelist


def test_whitelist_docstring_imperative():
    """Checks that the _whitelist function docstring is in the imperative mood."""
    docstring = vulture_whitelist._whitelist.__doc__
    assert docstring is not None, "Docstring should not be empty"
    assert docstring.strip().startswith("Hold vulture whitelist references.")
