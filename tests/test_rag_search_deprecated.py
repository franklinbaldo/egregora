"""Regression guard for the deprecated TF-IDF search module."""

from importlib import import_module


def test_rag_search_module_is_marked_deprecated() -> None:
    module = import_module("egregora.rag.search")
    assert module.__doc__
    assert module.__doc__.startswith("DEPRECATED"), module.__doc__
