"""TDD tests for refactoring RSSAdapter."""

from collections.abc import Callable

import pytest

from egregora_v3.infra.adapters.rss import RSSAdapter


def test_rss_adapter_uses_data_driven_dispatch():
    """Asserts that the adapter uses a data-driven dispatch table."""
    adapter = RSSAdapter()

    # Heuristic: Data over logic
    # Check for a dispatch table (e.g., a dict) instead of if/elif/else
    assert hasattr(adapter, "_feed_parsers")
    dispatch_table = getattr(adapter, "_feed_parsers")

    assert isinstance(dispatch_table, dict)
    assert len(dispatch_table) >= 2  # At least Atom and RSS

    # Check that the dispatch table maps to callable methods
    for parser_method in dispatch_table.values():
        assert isinstance(parser_method, Callable)
