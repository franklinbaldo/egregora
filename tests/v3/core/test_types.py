"""Tests for the core data types in Egregora V3."""

from datetime import datetime
import pytest
from egregora_v3.core.types import Document, DocumentType, DocumentStatus, Entry, Link
from egregora_v3.knowledge.concepts import WikiPage, ConceptType

def test_document_constructor_generates_identity():
    """Tests that the default Document constructor can generate id/slug."""
    now = datetime.now()
    doc = Document(
        title="Hello World",
        updated=now,
        content="This is a test.",
        doc_type=DocumentType.POST,
        status=DocumentStatus.DRAFT,
    )
    assert doc.id == "hello-world"
    assert doc.slug == "hello-world"
    assert doc.title == "Hello World"


def test_wikipage_constructor_creates_concept():
    """Tests that the WikiPage constructor can be used directly."""
    now = datetime.now()
    wikipage = WikiPage(
        title="Test Concept",
        updated=now,
        content="This is the body of the concept.",
        concept_type=ConceptType.TERM,
        evidence_refs=["doc1", "doc2"],
    )
    assert wikipage.id == "test-concept"
    assert wikipage.slug == "test-concept"
    assert wikipage.concept_type == ConceptType.TERM
    assert wikipage.doc_type == DocumentType.CONCEPT


def test_entry_has_enclosure_property():
    """Tests the has_enclosure property on the Entry model."""
    now = datetime.now()
    # Entry with no links
    entry_no_links = Entry(id="1", title="No Links", updated=now)
    assert not entry_no_links.has_enclosure
    # Entry with a non-enclosure link
    entry_other_link = Entry(
        id="2",
        title="Other Link",
        updated=now,
        links=[Link(href="http://example.com", rel="alternate")],
    )
    assert not entry_other_link.has_enclosure
    # Entry with an enclosure link
    entry_with_enclosure = Entry(
        id="3",
        title="With Enclosure",
        updated=now,
        links=[
            Link(
                href="http://example.com/image.jpg",
                rel="enclosure",
                type="image/jpeg",
            )
        ],
    )
    assert entry_with_enclosure.has_enclosure
    # Entry with multiple links, one of which is an enclosure
    entry_mixed_links = Entry(
        id="4",
        title="Mixed Links",
        updated=now,
        links=[
            Link(href="http://example.com", rel="alternate"),
            Link(
                href="http://example.com/image.jpg",
                rel="enclosure",
                type="image/jpeg",
            ),
        ],
    )
    assert entry_mixed_links.has_enclosure
