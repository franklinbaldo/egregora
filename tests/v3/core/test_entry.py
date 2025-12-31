from datetime import datetime, UTC
from egregora_v3.core.types import Entry
from egregora_v3.core.rendering import render_html

def test_render_html_renders_markdown():
    """Verify that the render_html function correctly renders Markdown."""
    content = "*Hello*, **world**! This is `code`."
    # The strip() call in the implementation removes the trailing newline
    expected_html = "<p><em>Hello</em>, <strong>world</strong>! This is <code>code</code>.</p>"
    assert render_html(content) == expected_html

def test_render_html_with_no_content():
    """Verify that render_html is None when content is None."""
    assert render_html(None) is None

def test_render_html_with_empty_content():
    """Verify that render_html returns None for empty content due to falsiness."""
    # An empty string is falsy, so the function returns None
    assert render_html("") is None
