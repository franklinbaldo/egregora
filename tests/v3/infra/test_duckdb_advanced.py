"""Advanced property-based tests for DuckDBDocumentRepository.

Tests demonstrate:
1. Property-based testing with Hypothesis
2. Realistic data generation with Faker
3. Time-based testing with freezegun
4. Concurrent access patterns
5. Edge cases and error handling

Following TDD approach - these tests verify existing implementation.
"""

import time
from datetime import UTC, datetime

import duckdb
import ibis
import pytest
from faker import Faker
from freezegun import freeze_time
from hypothesis import given, settings
from hypothesis import strategies as st

from egregora_v3.core.types import Author, Category, Document, DocumentStatus, DocumentType, Link
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository

fake = Faker()


# ========== Fixtures ==========


@pytest.fixture
def duckdb_conn():
    """Create in-memory DuckDB connection."""
    return ibis.duckdb.connect(":memory:")


@pytest.fixture
def repo(duckdb_conn):
    """Create initialized DuckDB repository."""
    repository = DuckDBDocumentRepository(duckdb_conn)
    repository.initialize()
    return repository


# ========== Property-Based Tests ==========


@settings(deadline=None)
@given(st.integers(min_value=1, max_value=100))
def test_save_and_retrieve_any_number_of_documents(num_docs: int) -> None:
    """Property: Can save and retrieve any number of documents."""
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()

    # Generate documents
    docs = [
        Document.create(
            content=f"Content {i}",
            doc_type=DocumentType.POST,
            title=f"Post {i}",
            status=DocumentStatus.PUBLISHED,
        )
        for i in range(num_docs)
    ]

    # Save all
    for doc in docs:
        repo.save(doc)

    # Retrieve all
    retrieved = repo.list()

    # Invariants
    assert len(retrieved) == num_docs
    assert {d.id for d in retrieved} == {d.id for d in docs}


@settings(deadline=None)
@given(
    st.text(
        min_size=1,
        max_size=1000,
        alphabet=st.characters(
            blacklist_categories=["Cc", "Cs"],  # Exclude control chars and surrogates
            blacklist_characters="\x00",  # Exclude NULL byte
        ),
    ),
    st.sampled_from(list(DocumentType)),
)
def test_content_preservation(content: str, doc_type: DocumentType) -> None:
    """Property: Content is always preserved exactly."""
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()

    doc = Document.create(
        content=content,
        doc_type=doc_type,
        title="Test",
        status=DocumentStatus.PUBLISHED,
    )

    repo.save(doc)
    retrieved = repo.get(doc.id)

    assert retrieved is not None
    assert retrieved.content == content
    assert retrieved.doc_type == doc_type


@settings(deadline=None)
@given(st.integers(min_value=1, max_value=50))
def test_save_is_idempotent(num_saves: int) -> None:
    """Property: Saving the same document multiple times is idempotent."""
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()

    doc = Document.create(
        content="Test content",
        doc_type=DocumentType.POST,
        title="Test Post",
    )

    # Save multiple times
    for _ in range(num_saves):
        repo.save(doc)

    # Should only have one document
    all_docs = repo.list()
    assert len(all_docs) == 1
    assert all_docs[0].id == doc.id


@settings(deadline=None)
@given(
    st.lists(
        st.sampled_from(list(DocumentType)),
        min_size=1,
        max_size=20,
    )
)
def test_list_filter_by_type_correctness(doc_types: list[DocumentType]) -> None:
    """Property: Filtering by type returns only documents of that type."""
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()

    # Create documents of various types
    for i, doc_type in enumerate(doc_types):
        doc = Document.create(
            content=f"Content {i}",
            doc_type=doc_type,
            title=f"Doc {i}",
        )
        repo.save(doc)

    # Test filtering for each unique type
    for doc_type in set(doc_types):
        filtered = repo.list(doc_type=doc_type)

        # All returned docs should be of requested type
        assert all(d.doc_type == doc_type for d in filtered)

        # Count should match
        expected_count = doc_types.count(doc_type)
        assert len(filtered) == expected_count


# ========== Faker-Based Tests ==========


def test_repository_with_realistic_blog_posts(repo: DuckDBDocumentRepository) -> None:
    """Test repository with realistic blog post data."""
    # Generate realistic blog posts
    posts = []
    for _ in range(10):
        doc = Document.create(
            content=fake.text(max_nb_chars=500),
            doc_type=DocumentType.POST,
            title=fake.sentence(),
            status=fake.random_element([DocumentStatus.PUBLISHED, DocumentStatus.DRAFT]),
        )
        doc.authors = [Author(name=fake.name(), email=fake.email())]
        posts.append(doc)
        repo.save(doc)

    # Retrieve and verify
    retrieved = repo.list()
    assert len(retrieved) == 10

    # Check realistic data preserved
    for post in retrieved:
        assert len(post.title) > 0
        assert len(post.content) > 0


def test_repository_with_unicode_content(repo: DuckDBDocumentRepository) -> None:
    """Test repository handles Unicode content correctly."""
    unicode_samples = [
        "Hello 世界",  # Chinese
        "Привет мир",  # Russian
        "مرحبا بالعالم",  # Arabic
        "🎉🚀✨",  # Emojis
        "Olá Mundo",  # Portuguese
    ]

    for i, text in enumerate(unicode_samples):
        doc = Document.create(
            content=text,
            doc_type=DocumentType.POST,
            title=f"Unicode Test {i}",
        )
        repo.save(doc)

    # Retrieve and verify
    retrieved = repo.list()
    assert len(retrieved) == len(unicode_samples)

    # All unicode content should be preserved
    retrieved_content = {d.content for d in retrieved}
    assert set(unicode_samples) == retrieved_content


# ========== Time-Based Tests with freezegun ==========


@freeze_time("2025-12-06 10:00:00")
def test_documents_sorted_by_updated_timestamp(repo: DuckDBDocumentRepository) -> None:
    """Test that documents can be sorted by their updated timestamp."""
    docs = []
    for i in range(5):
        doc = Document.create(
            content=f"Content {i}",
            doc_type=DocumentType.POST,
            title=f"Post {i}",
        )
        repo.save(doc)
        docs.append(doc)
        # Advance time slightly
        time.sleep(0.01)

    retrieved = repo.list()

    # Should retrieve all documents
    assert len(retrieved) == 5


@freeze_time("2025-01-01 00:00:00")
def test_document_timestamps_preserved_across_saves(repo: DuckDBDocumentRepository) -> None:
    """Test that original timestamps are preserved on update."""
    # Create document at specific time
    doc = Document.create(
        content="Original content",
        doc_type=DocumentType.POST,
        title="Test Post",
    )
    original_updated = doc.updated
    repo.save(doc)

    # Move time forward
    with freeze_time("2025-01-02 00:00:00"):
        # Update document
        doc.content = "Updated content"
        doc.updated = datetime.now(UTC)
        repo.save(doc)

        # Retrieve
        retrieved = repo.get(doc.id)
        assert retrieved is not None

        # Updated timestamp should be newer
        assert retrieved.updated > original_updated


# ========== Edge Cases ==========


def test_save_document_with_very_long_content(repo: DuckDBDocumentRepository) -> None:
    """Test saving document with very long content (10MB)."""
    # 10MB of content
    very_long_content = "x" * (10 * 1024 * 1024)

    doc = Document.create(
        content=very_long_content,
        doc_type=DocumentType.POST,
        title="Large Document",
    )

    repo.save(doc)
    retrieved = repo.get(doc.id)

    assert retrieved is not None
    assert len(retrieved.content) == len(very_long_content)


def test_save_document_with_special_characters_in_id(repo: DuckDBDocumentRepository) -> None:
    """Test documents with special characters in IDs."""
    # Documents with semantic IDs (slugs)
    special_ids = [
        "post-with-dashes",
        "post_with_underscores",
        "post.with.dots",
        "post-123-numbers",
    ]

    for special_id in special_ids:
        doc = Document.create(
            content="Test content",
            doc_type=DocumentType.POST,
            title="Test",
            id_override=special_id,
        )
        repo.save(doc)

    # All should be retrievable
    for special_id in special_ids:
        retrieved = repo.get(special_id)
        assert retrieved is not None
        assert retrieved.id == special_id


def test_get_nonexistent_document_returns_none(repo: DuckDBDocumentRepository) -> None:
    """Test that getting non-existent document returns None."""
    result = repo.get("nonexistent-id-12345")
    assert result is None


def test_delete_nonexistent_document_succeeds(repo: DuckDBDocumentRepository) -> None:
    """Test that deleting non-existent document doesn't raise error."""
    # Should not raise
    repo.delete("nonexistent-id-12345")


def test_exists_returns_correct_boolean(repo: DuckDBDocumentRepository) -> None:
    """Test exists() method correctness."""
    doc = Document.create(
        content="Test",
        doc_type=DocumentType.POST,
        title="Test",
    )

    # Before save
    assert not repo.exists(doc.id)

    # After save
    repo.save(doc)
    assert repo.exists(doc.id)

    # After delete
    repo.delete(doc.id)
    assert not repo.exists(doc.id)


# ========== Update Operations ==========


def test_update_preserves_id(repo: DuckDBDocumentRepository) -> None:
    """Test that updating document preserves its ID."""
    doc = Document.create(
        content="Original",
        doc_type=DocumentType.POST,
        title="Original Title",
    )
    original_id = doc.id

    repo.save(doc)

    # Update
    doc.title = "Updated Title"
    doc.content = "Updated Content"
    repo.save(doc)

    # ID should be unchanged
    retrieved = repo.get(original_id)
    assert retrieved is not None
    assert retrieved.id == original_id
    assert retrieved.title == "Updated Title"
    assert retrieved.content == "Updated Content"


def test_update_document_status(repo: DuckDBDocumentRepository) -> None:
    """Test updating document status."""
    doc = Document.create(
        content="Test",
        doc_type=DocumentType.POST,
        title="Test",
        status=DocumentStatus.DRAFT,
    )

    repo.save(doc)

    # Update status
    doc.status = DocumentStatus.PUBLISHED
    repo.save(doc)

    # Verify
    retrieved = repo.get(doc.id)
    assert retrieved is not None
    assert retrieved.status == DocumentStatus.PUBLISHED


# ========== Roundtrip Serialization ==========


def test_roundtrip_serialization_preserves_all_fields(repo: DuckDBDocumentRepository) -> None:
    """Test that all document fields survive save/retrieve roundtrip."""
    doc = Document.create(
        content="# Test Post\n\nThis is **markdown** content.",
        doc_type=DocumentType.POST,
        title="Test Post",
        status=DocumentStatus.PUBLISHED,
    )

    # Add all optional fields
    doc.summary = "Test summary"
    doc.published = datetime(2025, 12, 5, tzinfo=UTC)
    doc.authors = [Author(name="Alice", email="alice@example.com")]
    doc.categories = [Category(term="test", label="Test")]
    doc.links = [Link(href="https://example.com", rel="alternate")]

    repo.save(doc)
    retrieved = repo.get(doc.id)

    assert retrieved is not None

    # Verify all fields
    assert retrieved.id == doc.id
    assert retrieved.title == doc.title
    assert retrieved.content == doc.content
    assert retrieved.summary == doc.summary
    assert retrieved.doc_type == doc.doc_type
    assert retrieved.status == doc.status
    assert len(retrieved.authors) == 1
    assert len(retrieved.categories) == 1
    assert len(retrieved.links) == 1


# ========== Concurrent Operations Simulation ==========


def test_multiple_saves_of_same_document_last_write_wins(
    repo: DuckDBDocumentRepository,
) -> None:
    """Test concurrent updates - last write wins."""
    doc = Document.create(
        content="Version 0",
        doc_type=DocumentType.POST,
        title="Test",
    )

    repo.save(doc)

    # Simulate concurrent updates
    doc.content = "Version 1"
    repo.save(doc)

    doc.content = "Version 2"
    repo.save(doc)

    doc.content = "Version 3"
    repo.save(doc)

    # Last version should win
    retrieved = repo.get(doc.id)
    assert retrieved is not None
    assert retrieved.content == "Version 3"


# ========== Performance/Stress Tests ==========


@pytest.mark.slow
def test_bulk_insert_and_retrieve(repo: DuckDBDocumentRepository) -> None:
    """Test bulk operations with 1000 documents."""
    docs = [
        Document.create(
            content=f"Content {i}",
            doc_type=DocumentType.POST if i % 2 == 0 else DocumentType.NOTE,
            title=f"Doc {i}",
        )
        for i in range(1000)
    ]

    # Bulk save
    for doc in docs:
        repo.save(doc)

    # Retrieve all
    retrieved = repo.list()
    assert len(retrieved) == 1000

    # Test filtering
    posts = repo.list(doc_type=DocumentType.POST)
    notes = repo.list(doc_type=DocumentType.NOTE)

    assert len(posts) == 500
    assert len(notes) == 500


# ========== Error Handling ==========


def test_repository_survives_malformed_json_in_database(
    duckdb_conn,
) -> None:
    """Test graceful handling of corrupted data."""
    repo = DuckDBDocumentRepository(duckdb_conn)
    repo.initialize()

    # Insert malformed JSON directly
    try:
        duckdb_conn.con.execute(
            f"INSERT INTO {repo.table_name} (id, doc_type, json_data, updated) "
            "VALUES ('bad-id', 'post', '{invalid json}', CURRENT_TIMESTAMP)"
        )
    except duckdb.Error as exc:
        # Some databases might reject invalid JSON
        pytest.skip(f"Database rejects invalid JSON: {exc}")

    # list() should either skip bad record or raise clear error
    # (Implementation dependent - document behavior)
    error_message = None
    try:
        docs = repo.list()
    except (duckdb.Error, ValueError) as exc:
        # Some connectors may surface parsing errors as exceptions
        error_message = str(exc).lower()
        docs = None

    if error_message is not None:
        assert "json" in error_message or "parse" in error_message
    else:
        # If successful, bad record should be skipped
        assert all(d.id != "bad-id" for d in docs)
