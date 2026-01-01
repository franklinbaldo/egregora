from datetime import datetime, UTC

from egregora_v3.core.rendering import render_html_content
from egregora_v3.core.types import Entry


def test_entry_html_content():
    """Tests that the html_content property renders markdown correctly."""
    entry = Entry(
        id="test-entry",
        title="My Test Entry",
        updated=datetime.now(UTC),
        content="*Hello*, **world**!",
    )
    assert render_html_content(entry) == "<p><em>Hello</em>, <strong>world</strong>!</p>"
