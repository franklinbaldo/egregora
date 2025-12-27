"""Tests for the Concept models."""
from datetime import datetime
from egregora_v3.core.types import DocumentStatus
from egregora_v3.knowledge.concepts import WikiPage, ConceptType


def test_create_wiki_page_declaratively():
    """Ensures a WikiPage can be created declaratively without the factory."""
    now = datetime.now()
    page = WikiPage(
        title="The Noodle Incident",
        content="It was a dark and stormy night...",
        concept_type=ConceptType.EVENT,
        evidence_refs=["ref1", "ref2"],
        status=DocumentStatus.PUBLISHED,
        updated=now,
        published=now,
    )

    assert page.id == "the-noodle-incident"
    assert page.slug == "the-noodle-incident"
    assert page.title == "The Noodle Incident"
    assert page.doc_type == "concept"
