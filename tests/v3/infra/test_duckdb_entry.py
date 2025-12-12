from datetime import UTC, datetime

import ibis
import pytest

from egregora_v3.core.types import Author, Document, DocumentType, Entry, Link
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def repository():
    # Setup in-memory DuckDB connection
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()
    return repo


def test_save_and_get_entry(repository):
    entry = Entry(
        id="entry-1",
        title="Test Entry",
        updated=datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
        content="This is a test entry",
        authors=[Author(name="Tester")],
        links=[Link(href="http://example.com")],
    )

    repository.save_entry(entry)

    retrieved = repository.get_entry("entry-1")
    assert retrieved is not None
    assert retrieved.id == "entry-1"
    assert retrieved.title == "Test Entry"
    assert retrieved.content == "This is a test entry"
    assert len(retrieved.authors) == 1
    assert retrieved.authors[0].name == "Tester"
    assert isinstance(retrieved, Entry)
    # Ensure it's not a Document if we saved a raw Entry
    assert not isinstance(retrieved, Document)


def test_save_and_get_document_as_entry(repository):
    doc = Document(
        id="doc-1",
        title="Test Document",
        updated=datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
        content="This is a test document",
        doc_type=DocumentType.POST,
    )

    repository.save(doc)

    # get_entry should be able to retrieve it
    retrieved = repository.get_entry("doc-1")
    assert retrieved is not None
    assert retrieved.id == "doc-1"
    assert isinstance(retrieved, Entry)
    # It might come back as Document if we infer type from DB,
    # or as Entry if we just deserialize into Entry.
    # Given the implementation plan, if we store doc_type, we might want to rehydrate as Document.
    # But for now, let's just ensure it acts as an Entry.
    assert retrieved.title == "Test Document"


def test_get_entries_by_source(repository):
    # This requires Source to be set
    from egregora_v3.core.types import Source  # noqa: PLC0415

    source = Source(id="source-1", title="My Source")

    entry1 = Entry(id="e1", title="E1", updated=datetime.now(UTC), source=source)
    entry2 = Entry(id="e2", title="E2", updated=datetime.now(UTC), source=source)
    entry3 = Entry(id="e3", title="E3", updated=datetime.now(UTC), source=Source(id="source-2"))

    repository.save_entry(entry1)
    repository.save_entry(entry2)
    repository.save_entry(entry3)

    results = repository.get_entries_by_source("source-1")
    assert len(results) == 2
    ids = {e.id for e in results}
    assert "e1" in ids
    assert "e2" in ids
    assert "e3" not in ids
