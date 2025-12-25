import pytest
from datetime import datetime, timedelta, timezone

import ibis

from egregora_v3.core.types import Document, DocumentType
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def duckdb_repo() -> DuckDBDocumentRepository:
    """Provides an in-memory DuckDB repository for testing."""
    conn = ibis.duckdb.connect()
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()
    return repo


def test_list_with_order_by_and_limit(duckdb_repo: DuckDBDocumentRepository):
    """Tests that the list method correctly applies sorting and limiting."""
    # ARRANGE
    now = datetime.now(timezone.utc)
    docs = []
    for i in range(5):
        doc = Document.create(
            content=f"Post {i}",
            doc_type=DocumentType.POST,
            title=f"Post {i}",
        )
        doc.updated = now - timedelta(days=i)
        docs.append(doc)

    for doc in docs:
        duckdb_repo.save(doc)

    # ACT
    # Fetch the 3 most recent posts
    result = duckdb_repo.list(
        doc_type=DocumentType.POST, order_by="updated", limit=3
    )

    # ASSERT
    assert len(result) == 3
    assert result[0].title == "Post 0"  # Most recent
    assert result[1].title == "Post 1"
    assert result[2].title == "Post 2"

    # Check that they are sorted correctly (most recent first)
    assert result[0].updated > result[1].updated > result[2].updated
