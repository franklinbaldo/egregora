from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from egregora_v3.core.types import (
    Document,
    DocumentType,
    Feed,
    Entry,
    Author,
    Link,
    InReplyTo
)

# --- Strategies ---

def xml_safe_text(min_size=0, max_size=100):
    """Generate XML-safe text with configurable size limits.

    Default max_size reduced from 500 to 100 for faster property test execution.
    """
    return st.text(alphabet=st.characters(blacklist_categories=('Cc', 'Cs', 'Co')), min_size=min_size, max_size=max_size)

def document_strategy():
    return st.builds(
        Document.create,
        content=xml_safe_text(min_size=1),
        doc_type=st.sampled_from(DocumentType),
        title=xml_safe_text(min_size=1),
        slug=st.one_of(st.none(), st.text(min_size=1, alphabet=st.characters(whitelist_categories=('L', 'N')))),
        id_override=st.one_of(st.none(), st.text(min_size=1, alphabet=st.characters(whitelist_categories=('L', 'N')))),
        searchable=st.booleans(),
    )

def author_strategy():
    """Generate Author objects with optimized constraints.

    Uses simpler email generation for better performance.
    """
    # Simple email pattern instead of full st.emails() which can be slow
    simple_email = st.builds(
        lambda user, domain: f"{user}@{domain}",
        user=st.text(alphabet=st.characters(whitelist_categories=('L', 'N')), min_size=1, max_size=20),
        domain=st.sampled_from(['example.com', 'test.org', 'mail.net'])
    )
    return st.builds(
        Author,
        name=xml_safe_text(min_size=1, max_size=50),
        email=st.one_of(st.none(), simple_email)
    )

def entry_strategy():
    """Generate Entry objects with optimized constraints for faster tests.

    Reduced authors from max_size=3 to max_size=1 to minimize nested object generation.
    """
    return st.builds(
        Entry,
        id=xml_safe_text(min_size=1, max_size=50),
        title=xml_safe_text(min_size=1, max_size=50),
        updated=st.datetimes(timezones=st.just(timezone.utc)),
        content=xml_safe_text(max_size=200),
        authors=st.lists(author_strategy(), max_size=1),
        in_reply_to=st.one_of(
            st.none(),
            st.builds(InReplyTo, ref=xml_safe_text(min_size=1, max_size=50))
        )
    )

def feed_strategy():
    """Generate Feed objects with optimized constraints for faster tests.

    Reduced entries from max_size=5 to max_size=2 to minimize nested object generation.
    With max 2 entries and max 1 author each, we generate at most 2 nested objects,
    down from 15 (5 entries × 3 authors).
    """
    return st.builds(
        Feed,
        id=xml_safe_text(min_size=1, max_size=50),
        title=xml_safe_text(min_size=1, max_size=50),
        updated=st.datetimes(timezones=st.just(timezone.utc)),
        entries=st.lists(entry_strategy(), max_size=2)
    )

# --- Tests ---

@given(document_strategy())
def test_document_invariants(doc: Document):
    """Test core invariants for Document creation."""
    # 1. ID must exist
    assert doc.id is not None
    assert len(doc.id) > 0

    # 3. Slug behavior
    # Note: We rely on deterministic tests for Semantic Identity (slug == id)
    # because property-based testing with id_override makes this complex to assert.
    if doc.internal_metadata.get("slug"):
        pass

    # 3. Content addressing (Stability)
    # Re-creating the same doc (with no random ID/slug) should yield same ID
    # This is tricky with Property-Based testing because we don't know the inputs used.
    # We'll do a separate deterministic test for this.

def test_document_id_stability():
    """Ensure identical inputs produce identical IDs for UUIDv5 path."""
    content = "Hello world"
    title = "My Title"
    doc_type = DocumentType.NOTE

    doc1 = Document.create(content, doc_type, title)
    doc2 = Document.create(content, doc_type, title)

    assert doc1.id == doc2.id
    assert doc1.id != title # Should be a hash

def test_document_semantic_identity():
    """Ensure slug is used as ID for semantic types."""
    slug = "my-custom-slug"
    doc = Document.create(
        "content",
        DocumentType.POST,
        "Title",
        slug=slug
    )

    assert doc.id == slug
    assert doc.internal_metadata["slug"] == slug

@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(feed_strategy())
def test_feed_xml_validity(feed: Feed):
    """Test that generated XML is valid and parseable."""
    xml_str = feed.to_xml()

    # 1. Must be parseable
    root = ET.fromstring(xml_str)

    # 2. Namespace check
    # ElementTree parser strips namespaces in tag names usually like {uri}tag
    # Atom NS: http://www.w3.org/2005/Atom
    assert "feed" in root.tag

    # 3. Check for children
    assert root.find("{http://www.w3.org/2005/Atom}id") is not None
    assert root.find("{http://www.w3.org/2005/Atom}title") is not None

    # 4. Check Threading Namespace if present
    # This is harder to test with ElementTree simplistic API, but if it parsed, it's well-formed.

def test_threading_extension_xml():
    """Specific test for RFC 4685 threading output."""
    entry = Entry(
        id="child",
        title="Re: Parent",
        updated=datetime.now(timezone.utc),
        in_reply_to=InReplyTo(ref="parent-id", href="http://example.com/parent")
    )
    feed = Feed(
        id="feed",
        title="Thread Feed",
        updated=datetime.now(timezone.utc),
        entries=[entry]
    )

    xml_str = feed.to_xml()

    # We expect thr:in-reply-to
    assert 'xmlns:thr="http://purl.org/syndication/thread/1.0"' in xml_str
    assert '<thr:in-reply-to' in xml_str
    assert 'ref="parent-id"' in xml_str
