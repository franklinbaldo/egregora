import pytest
from datetime import datetime, UTC
from egregora_v3.core.types import Document, DocumentType, DocumentStatus, Feed, Entry

def test_document_create_generates_slug_from_title():
    """Verify that a slug is generated from the title if not provided."""
    doc = Document.create(
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


def test_document_create_uses_explicit_slug():
    """Verify that an explicit slug is used for the slug and ID."""
    doc = Document.create(
        content="Hello world",
        doc_type=DocumentType.POST,
        title="My First Post",
        slug="custom-slug"
    )
    assert doc.slug == "custom-slug"
    assert doc.id == "custom-slug"


def test_document_create_raises_error_on_empty_title_and_slug():
    """Verify that a ValueError is raised if a slug cannot be generated."""
    with pytest.raises(ValueError, match="Document must have a slug or a title to generate one."):
        Document.create(
            content="Hello world",
            doc_type=DocumentType.POST,
            title="",
            slug=""
        )

    # With the simplified logic, a title of "Untitled" with an explicit empty slug
    # should also fail, as the final slug is empty.
    with pytest.raises(ValueError, match="Document must have a slug or a title to generate one."):
        Document.create(
            content="Hello world",
            doc_type=DocumentType.POST,
            title="Untitled",
            slug=""
        )

def test_feed_to_xml_handles_document_and_entry():
    """Verify that Feed.to_xml correctly serializes both Entry and Document types."""
    now = datetime.now(UTC)

    doc = Document.create(
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

    # Assert that the Document-specific fields are present for the Document entry
    doc_type_category = f'<category term="{doc.doc_type.value}" scheme="https://egregora.app/schema#doc_type" label="Document Type" />'
    status_category = f'<category term="{doc.status.value}" scheme="https://egregora.app/schema#status" label="Document Status" />'

    assert f"<id>{doc.id}</id>" in xml_output
    assert doc_type_category in xml_output
    assert status_category in xml_output

    # Assert that the Document-specific fields are NOT present for the plain Entry
    entry_start_index = xml_output.find(f"<id>{entry.id}</id>")
    entry_end_index = xml_output.find("</entry>", entry_start_index)
    entry_xml_block = xml_output[entry_start_index:entry_end_index]

    assert "doc_type" not in entry_xml_block
    assert "status" not in entry_xml_block
