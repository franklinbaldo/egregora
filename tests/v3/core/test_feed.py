from datetime import UTC, datetime

import defusedxml.ElementTree as ET

from egregora_v3.core.types import (
    Document,
    DocumentStatus,
    DocumentType,
    Feed,
    documents_to_feed,
)


def test_feed_to_xml_exposes_doc_type_and_status_categories():
    doc = Document.create(
        content="Example body",
        doc_type=DocumentType.POST,
        title="Hello World",
        status=DocumentStatus.PUBLISHED,
    )
    doc.status = DocumentStatus.PUBLISHED

    feed = Feed(
        id="urn:egregora:feed:test",
        title="Test Feed",
        updated=doc.updated,
        entries=[doc],
    )

    xml_output = feed.to_xml()
    root = ET.fromstring(xml_output)
    entry = root.find("{http://www.w3.org/2005/Atom}entry")
    assert entry is not None

    categories = entry.findall("{http://www.w3.org/2005/Atom}category")
    exported_terms = {(cat.get("scheme"), cat.get("term")) for cat in categories}

    assert (
        "https://egregora.app/schema#doc_type",
        DocumentType.POST.value,
    ) in exported_terms
    assert (
        "https://egregora.app/schema#status",
        DocumentStatus.PUBLISHED.value,
    ) in exported_terms


def test_documents_to_feed_sorts_entries_newest_first():
    older = Document.create(
        content="Older entry",
        doc_type=DocumentType.NOTE,
        title="Older",
    )
    newer = Document.create(
        content="Newer entry",
        doc_type=DocumentType.NOTE,
        title="Newer",
    )

    older.updated = datetime(2024, 1, 1, tzinfo=UTC)
    newer.updated = datetime(2024, 1, 2, tzinfo=UTC)

    feed = documents_to_feed(
        [
            older,
            newer,
        ],
        feed_id="urn:egregora:feed:test",
        title="Test Feed",
    )

    assert feed.updated == newer.updated
    assert feed.entries[0].id == newer.id
