import pytest
from datetime import datetime, UTC
from pydantic import ValidationError
from egregora_v3.core.types import Document, DocumentType, DocumentStatus, Feed, Entry

def test_document_generates_slug_from_title():
    """Verify that a slug is generated from the title if not provided."""
    doc = Document(
        content="Hello world",
        doc_type=DocumentType.POST,
        title="  My First Post!  "
    )
    assert doc.slug == "my-first-post"
    assert doc.id == "my-first-post"
    assert doc.title == "  My First Post!  "
    assert doc.doc_type == DocumentType.POST
    assert doc.status == DocumentStatus.DRAFT
    assert isinstance(doc.updated, datetime)


def test_document_uses_explicit_slug():
    """Verify that an explicit slug is used for the slug and ID."""
    doc = Document(
        content="Hello world",
        doc_type=DocumentType.POST,
        title="My First Post",
        internal_metadata={"slug": "custom-slug"}
    )
    assert doc.slug == "custom-slug"
    assert doc.id == "custom-slug"


def test_document_raises_error_on_empty_title_and_slug():
    """Verify that a ValidationError is raised if an id cannot be generated."""
    with pytest.raises(ValidationError, match="Field required"):
        Document(
            content="Hello world",
            doc_type=DocumentType.POST,
            title=""
        )

    # An empty slug in metadata should also fail if there's no title
    with pytest.raises(ValidationError, match="Field required"):
        Document(
            content="Hello world",
            doc_type=DocumentType.POST,
            title="",
            internal_metadata={"slug": ""}
        )


def test_feed_to_xml_handles_document_and_entry():
    """Verify that Feed.to_xml correctly serializes both Entry and Document types."""
    now = datetime.now(UTC)

    doc = Document(
        content="This is a document.",
        doc_type=DocumentType.POST,
        title="A Document"
    )

    entry = Entry(
        id="plain-entry-1",
        title="A Plain Entry",
        updated=now
    )

    feed = Feed(
        id="test-feed",
        title="My Test Feed",
        updated=now,
        entries=[doc, entry]
    )

    xml_output = feed.to_xml()

    # Find the <entry> block for the document to check its contents
    doc_id_tag = f"<id>{doc.id}</id>"
    assert doc_id_tag in xml_output, "Document ID not found in feed XML"

    doc_entry_start = xml_output.rfind("<entry>", 0, xml_output.find(doc_id_tag))
    doc_entry_end = xml_output.find("</entry>", doc_entry_start)
    doc_xml_block = xml_output[doc_entry_start:doc_entry_end]

    # Assert that the Document-specific categories are present
    assert f'term="{doc.doc_type.value}"' in doc_xml_block
    assert 'scheme="https://egregora.app/schema#doc_type"' in doc_xml_block
    assert 'label="Document Type"' in doc_xml_block

    assert f'term="{doc.status.value}"' in doc_xml_block
    assert 'scheme="https://egregora.app/schema#status"' in doc_xml_block
    assert 'label="Document Status"' in doc_xml_block

    # Assert that the Document-specific fields are NOT present for the plain Entry
    entry_start_index = xml_output.find(f"<id>{entry.id}</id>")
    entry_end_index = xml_output.find("</entry>", entry_start_index)
    entry_xml_block = xml_output[entry_start_index:entry_end_index]

    assert "doc_type" not in entry_xml_block
    assert "status" not in entry_xml_block
