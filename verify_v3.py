"""Verification script for Egregora V3 Infrastructure."""

import ibis
import shutil
import math
from pathlib import Path
from datetime import datetime, timezone

from egregora_v3.core.types import Document, DocumentType, DocumentStatus
from egregora_v3.infra.repository import DuckDBRepository
from egregora.data_primitives.document import Document as LegacyDocument
from egregora.data_primitives.document import DocumentType as LegacyType

def verify_v3_infra():
    print("Initializing V3 Infrastructure Verification...")

    # Setup temporary DuckDB
    db_path = Path("v3_test.duckdb")
    if db_path.exists():
        db_path.unlink()

    con = ibis.duckdb.connect(str(db_path))
    repo = DuckDBRepository(con)

    print("Repository initialized.")

    # 1. Test V3 Document
    doc = Document.create(
        content="Test Content",
        doc_type=DocumentType.POST,
        title="Test Post",
        collection="posts",
        slug="test-semantic-slug",
        searchable=True,
        embedding=[0.1, 0.2, 0.3]
    )

    print(f"Created V3 Document: ID={doc.id}, Collection={doc.collection}")

    # Save
    repo.save(doc)
    print("V3 Document saved.")

    # Retrieve
    retrieved = repo.get(doc.id)
    assert retrieved is not None
    assert retrieved.id == "test-semantic-slug"
    assert retrieved.title == "Test Post"

    # Check embeddings (approximate)
    expected = [0.1, 0.2, 0.3]
    for r, e in zip(retrieved.embedding, expected):
        assert math.isclose(r, e, rel_tol=1e-5)

    assert retrieved.searchable is True
    print("V3 Document retrieved and verified.")

    # 2. Test Legacy Document Conversion
    legacy_doc = LegacyDocument(
        content="Legacy Content",
        type=LegacyType.POST,
        metadata={"title": "Legacy Post", "slug": "legacy-post-id"},
        id="legacy-post-id" # New semantic ID field we added to legacy doc
    )

    print(f"Created Legacy Document: ID={legacy_doc.document_id}")
    repo.save(legacy_doc)
    print("Legacy Document saved (converted).")

    retrieved_legacy = repo.get("legacy-post-id")
    assert retrieved_legacy is not None
    assert retrieved_legacy.title == "Legacy Post"
    assert retrieved_legacy.doc_type == DocumentType.POST
    # Default legacy collection logic
    assert retrieved_legacy.collection == "posts"
    print("Legacy Document retrieved and verified.")


    # High Water Mark
    hwm = repo.get_high_water_mark("posts")
    print(f"High Water Mark: {hwm}")
    assert hwm is not None

    # Cleanup
    if db_path.exists():
        db_path.unlink()

    print("Verification Complete: Success!")

if __name__ == "__main__":
    verify_v3_infra()
