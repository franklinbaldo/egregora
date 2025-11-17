"""Tests for EleventyArrowAdapter."""

import tempfile
from pathlib import Path

import ibis
import pyarrow.parquet as pq
import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters import create_output_format
from egregora.output_adapters.eleventy_arrow import EleventyArrowAdapter


def test_serve_and_finalize_writes_parquet():
    """Test that serve() buffers documents and finalize_window() writes Parquet."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_root = Path(tmpdir)
        adapter = EleventyArrowAdapter(site_root=site_root, url_context=None)

        # Create test documents with source_window
        doc1 = Document(
            content="# Post 1\n\nContent...",
            type=DocumentType.POST,
            metadata={"title": "Post 1", "slug": "post-1"},
            source_window="2025-01-11 10:00 to 12:00",
        )
        doc2 = Document(
            content="# Post 2\n\nMore content...",
            type=DocumentType.POST,
            metadata={"title": "Post 2", "slug": "post-2"},
            source_window="2025-01-11 10:00 to 12:00",
        )

        # Serve documents
        adapter.serve(doc1)
        adapter.serve(doc2)

        # Finalize window
        adapter.finalize_window("2025-01-11 10:00 to 12:00", [], [], {"window_index": 0})

        # Check Parquet file was created
        parquet_path = site_root / "data" / "window_0.parquet"
        assert parquet_path.exists()

        # Read and verify contents
        table = pq.read_table(parquet_path)
        assert len(table) == 2

        # Convert to pandas for easier assertions
        df = table.to_pandas()
        assert df["kind"].tolist() == ["post", "post"]
        assert df["title"].tolist() == ["Post 1", "Post 2"]
        assert df["slug"].tolist() == ["post-1", "post-2"]


def test_serve_without_source_window_raises():
    """Test that serve() raises if document.source_window is not set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_root = Path(tmpdir)
        adapter = EleventyArrowAdapter(site_root=site_root, url_context=None)

        # Create document without source_window
        doc = Document(
            content="# Post\n\nContent...",
            type=DocumentType.POST,
            metadata={"title": "Post"},
        )

        with pytest.raises(RuntimeError, match="Document must have source_window"):
            adapter.serve(doc)


def test_multiple_windows():
    """Test that multiple windows create separate Parquet files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_root = Path(tmpdir)
        adapter = EleventyArrowAdapter(site_root=site_root, url_context=None)

        # Window 0
        doc1 = Document(
            content="# Post 1",
            type=DocumentType.POST,
            metadata={"title": "Post 1", "slug": "post-1"},
            source_window="window_0",
        )
        adapter.serve(doc1)
        adapter.finalize_window("window_0", [], [], {"window_index": 0})

        # Window 1
        doc2 = Document(
            content="# Post 2",
            type=DocumentType.POST,
            metadata={"title": "Post 2", "slug": "post-2"},
            source_window="window_1",
        )
        adapter.serve(doc2)
        adapter.finalize_window("window_1", [], [], {"window_index": 1})

        # Check both files exist
        assert (site_root / "data" / "window_0.parquet").exists()
        assert (site_root / "data" / "window_1.parquet").exists()

        # Verify contents
        table0 = pq.read_table(site_root / "data" / "window_0.parquet")
        table1 = pq.read_table(site_root / "data" / "window_1.parquet")

        assert len(table0) == 1
        assert len(table1) == 1
        assert table0.to_pandas()["title"].tolist() == ["Post 1"]
        assert table1.to_pandas()["title"].tolist() == ["Post 2"]


def test_empty_window():
    """Test that finalize_window() handles empty windows gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_root = Path(tmpdir)
        adapter = EleventyArrowAdapter(site_root=site_root, url_context=None)

        # Finalize without any documents
        adapter.finalize_window("empty_window", [], [], {"window_index": 0})

        # No Parquet file should be created
        parquet_path = site_root / "data" / "window_0.parquet"
        assert not parquet_path.exists()


def test_read_document():
    """Test read_document() can retrieve documents from Parquet."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_root = Path(tmpdir)
        adapter = EleventyArrowAdapter(site_root=site_root, url_context=None)

        # Create and serve document
        doc = Document(
            content="# My Post\n\nContent...",
            type=DocumentType.POST,
            metadata={"title": "My Post", "slug": "my-post"},
            source_window="window_0",
        )
        adapter.serve(doc)
        adapter.finalize_window("window_0", [], [], {"window_index": 0})

        # Read back by slug
        retrieved = adapter.read_document(DocumentType.POST, "my-post")
        assert retrieved is not None
        assert retrieved.content == "# My Post\n\nContent..."
        assert retrieved.type == DocumentType.POST
        assert retrieved.metadata["title"] == "My Post"


def test_read_profile_document_by_uuid():
    """Profiles should be retrievable using their UUID metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_root = Path(tmpdir)
        adapter = EleventyArrowAdapter(site_root=site_root, url_context=None)

        profile = Document(
            content="Profile biography",
            type=DocumentType.PROFILE,
            metadata={"uuid": "author-123"},
            source_window="window_0",
        )

        adapter.serve(profile)
        adapter.finalize_window("window_0", [], [], {"window_index": 0})

        retrieved = adapter.read_document(DocumentType.PROFILE, "author-123")
        assert retrieved is not None
        assert retrieved.type == DocumentType.PROFILE
        assert retrieved.metadata["uuid"] == "author-123"


def test_list_documents():
    """Test list_documents() returns all documents across windows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_root = Path(tmpdir)
        adapter = EleventyArrowAdapter(site_root=site_root, url_context=None)

        # Create documents across two windows
        for i in range(3):
            doc = Document(
                content=f"# Post {i}",
                type=DocumentType.POST,
                metadata={"title": f"Post {i}", "slug": f"post-{i}"},
                source_window=f"window_{i % 2}",
            )
            adapter.serve(doc)

        adapter.finalize_window("window_0", [], [], {"window_index": 0})
        adapter.finalize_window("window_1", [], [], {"window_index": 1})

        # List all documents
        all_docs = adapter.list_documents()
        assert len(all_docs) == 3

        # Filter by type
        posts = adapter.list_documents(doc_type=DocumentType.POST)
        assert len(posts) == 3


def test_create_output_format_registers_eleventy_arrow(tmp_path: Path):
    """create_output_format should instantiate the Eleventy Arrow adapter."""

    site_root = tmp_path
    adapter = create_output_format(site_root, format_type="eleventy-arrow")

    assert adapter.format_type == "eleventy-arrow"

    window_ctx = adapter.prepare_window("window_0") or {"window_index": 0}

    doc = Document(
        content="# Title\n\nBody",
        type=DocumentType.POST,
        metadata={"title": "Title", "slug": "post-1"},
        source_window="window_0",
    )

    adapter.serve(doc)
    adapter.finalize_window("window_0", [], [], window_ctx)

    parquet_path = site_root / "data" / "window_0.parquet"
    assert parquet_path.exists()

    table = adapter.list_documents()
    assert isinstance(table, ibis.expr.types.Table)
    assert table.count().execute() == 1

    df = table.execute()
    identifier = df.iloc[0]["storage_identifier"]
    cache_path = adapter.resolve_document_path(identifier)
    assert cache_path.exists()
    assert "Title" in cache_path.read_text(encoding="utf-8")
