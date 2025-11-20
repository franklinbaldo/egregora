"""Extended E2E tests for Reader Agent and Eleventy Arrow Output Adapter.

These tests cover the post evaluation/ranking loop and the high-performance
Parquet-based output adapter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from egregora.agents.reader.models import PostComparison, ReaderFeedback
from egregora.agents.reader.reader_runner import run_reader_evaluation
from egregora.config.settings import ReaderSettings
from egregora.data_primitives.document import Document, DocumentType
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.elo_store import EloStore
from egregora.output_adapters.eleventy_arrow.adapter import EleventyArrowAdapter

# =============================================================================
# TEST: Reader Agent E2E (Evaluation & Ranking)
# =============================================================================


@pytest.mark.asyncio
async def test_e2e_reader_evaluation(tmp_path: Path) -> None:
    """Verify the post evaluation loop: finding posts, pairing them,
    getting AI judgment, and updating ELO ratings in DuckDB.
    """
    # 1. Setup Site & Posts
    site_root = tmp_path / "reader_site"
    posts_dir = site_root / "posts"
    posts_dir.mkdir(parents=True)

    # Create 3 dummy posts
    (posts_dir / "post1.md").write_text("# Post 1\nContent A", encoding="utf-8")
    (posts_dir / "post2.md").write_text("# Post 2\nContent B", encoding="utf-8")
    (posts_dir / "post3.md").write_text("# Post 3\nContent C", encoding="utf-8")

    # Create config
    config = ReaderSettings(
        enabled=True,
        comparisons_per_post=1,  # Minimal comparisons for test
        k_factor=32,
        database_path=".egregora/reader.duckdb",
    )

    # 2. Mock the AI Comparison Agent
    # We mock `compare_posts` to avoid calling Gemini
    with patch("egregora.agents.reader.reader_runner.compare_posts") as mock_compare:
        # Define a deterministic winner (Post 1 always wins)
        def side_effect(request, **kwargs):
            return PostComparison(
                post_a_slug=request.post_a_slug,
                post_b_slug=request.post_b_slug,
                winner="a",
                reasoning="Post A is more detailed.",
                feedback_a=ReaderFeedback(
                    comment="Good",
                    star_rating=5,
                    engagement_level="high",
                ),
                feedback_b=ReaderFeedback(
                    comment="Okay",
                    star_rating=3,
                    engagement_level="medium",
                ),
            )

        mock_compare.side_effect = side_effect

        # 3. Run Evaluation
        rankings = await run_reader_evaluation(posts_dir=posts_dir, config=config)

    # 4. Verification

    # A. Rankings were generated
    assert len(rankings) > 0

    # B. Check Database Persistence
    db_path = site_root / ".egregora" / "reader.duckdb"
    assert db_path.exists()

    # Use context manager for DuckDBStorageManager
    with DuckDBStorageManager(db_path=db_path) as storage:
        store = EloStore(storage)

        # Check top posts
        top_posts = store.get_top_posts(limit=10).execute()
        assert len(top_posts) > 0

        # Verify Elo updates occurred (ratings changed from default 1500)
        # The top-rated post should have rating > 1500 (it won at least once)
        top_rating = top_posts.iloc[0]["rating"]
        assert top_rating > 1500, f"Top post should have rating > 1500, got {top_rating}"

        # Verify wins were recorded for the top post
        top_wins = top_posts.iloc[0]["wins"]
        assert top_wins >= 1, f"Top post should have at least 1 win, got {top_wins}"

        # Check History
        history = store.get_comparison_history().execute()
        assert len(history) > 0


# =============================================================================
# TEST: Eleventy Arrow Output Adapter E2E
# =============================================================================


def test_e2e_output_adapter_eleventy(tmp_path: Path) -> None:
    """Verify the High-Performance Output Adapter:
    - Buffers documents in memory per window
    - Writes columnar Parquet files
    - Supports schema-less document retrieval
    """
    # 1. Setup
    site_root = tmp_path / "eleventy_site"
    adapter = EleventyArrowAdapter(site_root=site_root, url_context=None)

    # 2. Create Documents
    # We simulate processing two different windows
    now = datetime.now(UTC)

    # Window 1 Documents
    doc1 = Document(
        content="# Post 1",
        type=DocumentType.POST,
        metadata={"slug": "p1", "title": "Post 1"},
        source_window="2025-01-01",
        created_at=now,
    )
    doc2 = Document(
        content="Profile A",
        type=DocumentType.PROFILE,
        metadata={"uuid": "u1"},
        source_window="2025-01-01",
        created_at=now,
    )

    # Window 2 Document
    doc3 = Document(
        content="# Post 2",
        type=DocumentType.POST,
        metadata={"slug": "p2", "title": "Post 2"},
        source_window="2025-01-02",
        created_at=now,
    )

    # 3. Serve & Finalize

    # Serve documents (buffers them)
    adapter.serve(doc1)
    adapter.serve(doc2)
    adapter.serve(doc3)

    # Finalize Window 1
    # Use prepare_window to get window_index metadata
    metadata1 = adapter.prepare_window("2025-01-01")
    adapter.finalize_window("2025-01-01", [], [], metadata1)

    # Finalize Window 2
    metadata2 = adapter.prepare_window("2025-01-02")
    adapter.finalize_window("2025-01-02", [], [], metadata2)

    # 4. Verification

    data_dir = site_root / "data"
    assert data_dir.exists()

    parquet_files = sorted(data_dir.glob("*.parquet"))
    assert len(parquet_files) == 2

    # Inspect Parquet content
    # Window 0
    df0 = pd.read_parquet(parquet_files[0])
    assert len(df0) == 2
    assert "p1" in df0[df0["kind"] == "post"]["slug"].to_numpy()
    # Check profile UUID is in metadata
    profile_rows = df0[df0["kind"] == "profile"]
    assert len(profile_rows) > 0
    assert "u1" in str(profile_rows["metadata"].to_numpy())

    # Window 1
    df1 = pd.read_parquet(parquet_files[1])
    assert len(df1) == 1
    assert df1.iloc[0]["slug"] == "p2"

    # 5. Test Retrieval (Adapter Logic)
    # The adapter must be able to find the document inside the parquet files
    retrieved_doc = adapter.read_document(DocumentType.POST, "p1")
    assert retrieved_doc is not None
    assert retrieved_doc.content == "# Post 1"

    retrieved_doc_2 = adapter.read_document(DocumentType.POST, "p2")
    assert retrieved_doc_2 is not None
    assert retrieved_doc_2.content == "# Post 2"

    missing_doc = adapter.read_document(DocumentType.POST, "p99")
    assert missing_doc is None
