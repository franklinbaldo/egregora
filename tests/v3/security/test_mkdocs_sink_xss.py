"""Test for XSS vulnerabilities in the MkDocs output sink."""

from pathlib import Path
from datetime import datetime, timezone
import pytest
from egregora_v3.core.types import Document, Feed, DocumentStatus, Author, DocumentType
from egregora_v3.infra.sinks.mkdocs import MkDocsOutputSink


def test_xss_in_title_is_escaped(tmp_path: Path):
    """Verify that document titles with HTML are properly escaped to prevent XSS."""
    # 1. Arrange: Create a document with a malicious title
    malicious_title = 'Hello <script>alert("XSS")</script> World'
    xss_document = Document(
        id="doc:1",
        title=malicious_title,
        content="This is a test document.",
        authors=[Author(name="Attacker")],
        status=DocumentStatus.PUBLISHED,
        doc_type=DocumentType.POST,
        updated=datetime.now(timezone.utc),
        published=datetime.now(timezone.utc),
    )

    feed = Feed(
        id="feed:1",
        title="Test Feed",
        entries=[xss_document],
        updated=datetime.now(timezone.utc),
    )

    # 2. Act: Publish the feed using the sink
    output_dir = tmp_path / "site"
    sink = MkDocsOutputSink(output_dir=output_dir)
    sink.publish(feed)

    # 3. Assert: Check if the output is properly escaped
    index_file = output_dir / "index.md"
    assert index_file.exists()

    content = index_file.read_text(encoding="utf-8")

    # The exploit: The unescaped script tag should NOT be in the output.
    # This assertion will FAIL before the fix is applied.
    assert "<script>" not in content

    # The correct behavior: The title should be present but escaped.
    escaped_title = 'Hello &lt;script&gt;alert(&#34;XSS&#34;)&lt;/script&gt; World'
    assert escaped_title in content
