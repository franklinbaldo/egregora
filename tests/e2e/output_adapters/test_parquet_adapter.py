"""E2E tests for Parquet output adapter."""

from __future__ import annotations

import datetime
from pathlib import Path

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.parquet.adapter import ParquetAdapter


def test_parquet_adapter_persist_and_get(tmp_path: Path):
    """Test that the Parquet adapter can persist and retrieve a document."""
    # 1. Setup
    site_root = tmp_path
    adapter = ParquetAdapter()
    adapter.initialize(site_root)

    # 2. Create a document
    document = Document(
        content="This is the content of the document.",
        type=DocumentType.POST,
        metadata={
            "title": "Test Post",
            "slug": "test-post",
            "date": datetime.date(2025, 1, 1),
            "authors": ["author1", "author2"],
            "tags": ["tag1", "tag2"],
        },
        created_at=datetime.datetime.now(datetime.UTC),
    )
    doc_id = document.document_id

    # 3. Persist the document
    adapter.persist(document)

    # 4. Verify the file was created
    data_dir = site_root / "data"
    post_dir = data_dir / "type=post"
    parquet_file = post_dir / f"id={doc_id}.parquet"
    assert parquet_file.exists()

    # 5. Retrieve the document
    retrieved_doc = adapter.get(DocumentType.POST, doc_id)

    # 6. Assertions
    assert retrieved_doc is not None
    assert retrieved_doc.content == document.content
    assert retrieved_doc.metadata["title"] == document.metadata["title"]
    assert retrieved_doc.metadata["slug"] == document.metadata["slug"]
