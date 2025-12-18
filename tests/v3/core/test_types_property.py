from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import pytest
from hypothesis import given, strategies as st

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

def document_strategy():
    return st.builds(
        Document.create,
        content=st.text(min_size=1),
        doc_type=st.sampled_from(DocumentType),
        title=st.text(min_size=1),
        slug=st.one_of(st.none(), st.text(min_size=1, alphabet=st.characters(whitelist_categories=('L', 'N')))),
        id_override=st.one_of(st.none(), st.text(min_size=1)),
        searchable=st.booleans(),
    )

def author_strategy():
    return st.builds(Author, name=st.text(min_size=1), email=st.one_of(st.none(), st.emails()))

def entry_strategy():
    return st.builds(
        Entry,
        id=st.text(min_size=1),
        title=st.text(min_size=1),
        updated=st.datetimes(timezones=st.just(timezone.utc)),
        content=st.text(),
        authors=st.lists(author_strategy(), max_size=3),
        in_reply_to=st.one_of(
            st.none(),
            st.builds(InReplyTo, ref=st.text(min_size=1))
        )
    )

def feed_strategy():
    return st.builds(
        Feed,
        id=st.text(min_size=1),
        title=st.text(min_size=1),
        updated=st.datetimes(timezones=st.just(timezone.utc)),
        entries=st.lists(entry_strategy(), max_size=5)
    )

# --- Tests ---

@given(document_strategy())
def test_document_invariants(doc: Document):
    """Test core invariants for Document creation."""
    # 1. ID must exist
    assert doc.id is not None
    assert len(doc.id) > 0

    # 2. Slug behavior
    if doc.internal_metadata.get("slug"):
        # If we have a slug, and it's a semantic type, the ID might match the slug
        if doc.doc_type in (DocumentType.POST, DocumentType.MEDIA):
             # Note: slugify might change the input slug, so we can't assert strict equality
             # against the input, but we can assert the ID matches the PERSISTED slug
             assert doc.id == doc.internal_metadata["slug"]

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
