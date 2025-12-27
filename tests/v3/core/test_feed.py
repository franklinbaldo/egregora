from datetime import UTC, datetime

from defusedxml import ElementTree

from egregora_v3.core.types import Document, DocumentStatus, DocumentType, Feed, documents_to_feed, Entry


def test_feed_to_xml_exposes_doc_type_and_status_categories():
    doc = Document(
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
    root = ElementTree.fromstring(xml_output)
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
    older = Document(
        content="Older entry",
        doc_type=DocumentType.NOTE,
        title="Older",
    )
    newer = Document(
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


def test_feed_to_xml_handles_mixed_entry_types():
    """Ensures that only Documents get special category tags."""
    doc = Document(
        content="A document.",
        doc_type=DocumentType.POST,
        title="Document Title",
    )
    entry = Entry(
        id="urn:uuid:1234",
        title="Plain Entry",
        updated=datetime.now(UTC),
    )

    feed = Feed(
        id="urn:egregora:feed:mixed",
        title="Mixed Feed",
        updated=doc.updated,
        entries=[doc, entry],
    )

    xml_output = feed.to_xml()
    root = ElementTree.fromstring(xml_output)

    doc_entry_xml = None
    plain_entry_xml = None
    for e in root.findall("{http://www.w3.org/2005/Atom}entry"):
        entry_id = e.find("{http://www.w3.org/2005/Atom}id").text
        if entry_id == doc.id:
            doc_entry_xml = e
        elif entry_id == entry.id:
            plain_entry_xml = e

    # Check the Document entry
    assert doc_entry_xml is not None, "Document entry not found in feed XML"
    doc_categories = doc_entry_xml.findall("{http://www.w3.org/2005/Atom}category")
    doc_terms = {cat.get("term") for cat in doc_categories}
    assert DocumentType.POST.value in doc_terms
    assert DocumentStatus.DRAFT.value in doc_terms

    # Check the plain Entry
    assert plain_entry_xml is not None, "Plain entry not found in feed XML"
    plain_categories = plain_entry_xml.findall("{http://www.w3.org/2005/Atom}category")
    assert not plain_categories, "Plain entry should not have any categories"
