import pytest
from datetime import datetime, UTC
from pydantic import ValidationError
from freezegun import freeze_time
from egregora_v3.core.types import Author, Document, DocumentType, DocumentStatus, Feed, Entry

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

    # Assert that the Document-specific fields are present for the Document entry
    # The order of attributes is not guaranteed, so we check for parts
    assert f"<id>{doc.id}</id>" in xml_output
    assert 'term="post"' in xml_output
    assert 'scheme="https://egregora.app/schema#doc_type"' in xml_output
    assert 'term="draft"' in xml_output
    assert 'scheme="https://egregora.app/schema#status"' in xml_output

    # Assert that the Document-specific fields are NOT present for the plain Entry
    entry_start_index = xml_output.find(f"<id>{entry.id}</id>")
    entry_end_index = xml_output.find("</entry>", entry_start_index)
    entry_xml_block = xml_output[entry_start_index:entry_end_index]

    assert "doc_type" not in entry_xml_block
    assert "status" not in entry_xml_block


@freeze_time("2023-01-01T12:00:00Z")
def test_feed_to_xml_snapshot(snapshot):
    """Verify Feed.to_xml serialization against a snapshot."""
    feed = Feed(
        id="urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6",
        title="Example Feed",
        updated=datetime.now(UTC),
        authors=[Author(name="John Doe", email="johndoe@example.com")],
        links=[{"href": "http://example.org/", "rel": "alternate"}],
        entries=[
            Document(
                title="Atom-Powered Robots Run Amok",
                id="urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a",
                updated=datetime(2023, 1, 1, 11, 59, 59, tzinfo=UTC),
                published=datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC),
                authors=[Author(name="Jane Doe", email="janedoe@example.com")],
                summary="Some text.",
                content="This is the content.",
                content_type="text/markdown",
                doc_type=DocumentType.POST,
                status=DocumentStatus.PUBLISHED,
            ),
            Entry(
                title="A regular entry",
                id="urn:uuid:1225c695-cfb8-4ebb-bbbb-80da344efa6b",
                updated=datetime(2023, 1, 1, 9, 0, 0, tzinfo=UTC),
            ),
        ],
    )

    xml_output = feed.to_xml()
    assert xml_output == snapshot
