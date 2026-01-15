"""Unit tests for writer agent helper functions, focusing on error handling."""

from unittest.mock import MagicMock, patch

from egregora.agents.writer_helpers import (
    _get_cached_rag_context,
    _run_rag_query,
    _store_rag_context,
)


def test_run_rag_query_handles_connection_error():
    """Test that _run_rag_query handles ConnectionError."""
    with patch("egregora.agents.writer_helpers.search") as mock_search:
        mock_search.side_effect = ConnectionError("Connection refused")
        result = _run_rag_query("test query", 5)
        assert result is None


def test_run_rag_query_handles_value_error():
    """Test that _run_rag_query handles ValueError."""
    with patch("egregora.agents.writer_helpers.search") as mock_search:
        mock_search.side_effect = ValueError("Invalid query")
        result = _run_rag_query("test query", 5)
        assert result is None


def test_run_rag_query_handles_attribute_error():
    """Test that _run_rag_query handles AttributeError."""
    with patch("egregora.agents.writer_helpers.search") as mock_search:
        mock_search.side_effect = AttributeError("Malformed response")
        result = _run_rag_query("test query", 5)
        assert result is None


def test_get_cached_rag_context_handles_attribute_error():
    """Test that _get_cached_rag_context handles AttributeError."""
    mock_cache = MagicMock()
    mock_cache.rag.get.side_effect = AttributeError("Cache unavailable")
    result = _get_cached_rag_context(mock_cache, "test query")
    assert result is None


def test_store_rag_context_handles_attribute_error():
    """Test that _store_rag_context handles AttributeError."""
    mock_cache = MagicMock()
    mock_cache.rag.set.side_effect = AttributeError("Cache unavailable")
    # This function does not return a value, so we just check that it doesn't raise
    _store_rag_context(mock_cache, "test query", "test context")
