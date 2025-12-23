"""Tests for the writer agent."""

def test_writer_module_imports():
    """Test that the writer module can be imported."""
    from egregora.agents.writer import write_posts_for_window
    assert write_posts_for_window is not None
