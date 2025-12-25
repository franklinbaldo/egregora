"""Tests for the core data types in Egregora V3."""

from datetime import datetime
import pytest
from egregora_v3.core.types import Document, DocumentType, DocumentStatus
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
