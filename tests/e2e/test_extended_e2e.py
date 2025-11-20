"""E2E tests for quality feedback loop and high-performance output storage.

These tests validate two critical production capabilities:

1. **Reader Agent Quality Loop** - Validates that the system can evaluate post
   quality using AI-driven comparisons, update ELO ratings, and persist results.
   This is essential for:
   - Automated content quality assessment
   - Identifying top-performing posts for promotion
   - Providing feedback to improve future content generation

2. **Eleventy Arrow Output Adapter** - Validates the Parquet-based storage system
   for Eleventy static sites. This is essential for:
   - High-performance incremental publishing (no intermediate markdown files)
   - Column-oriented storage for efficient filtering/querying
   - Memory-efficient per-window document batching
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
# Reader Agent: Quality Feedback Loop
# =============================================================================


@pytest.mark.asyncio
async def test_reader_agent_evaluates_posts_and_persists_elo_rankings(tmp_path: Path) -> None:
    """Validate that Reader Agent can evaluate posts and persist quality rankings.

    Why this matters:
    - The Reader Agent enables automated quality assessment of generated content
    - ELO ratings help identify which posts resonate best with readers
    - Persistent ratings enable tracking quality trends over time
    - This feedback loop is essential for improving content generation

    What we test:
    1. Post discovery from filesystem
    2. AI-driven pairwise comparison (mocked)
    3. ELO rating calculation and updates
    4. Database persistence of ratings and comparison history
    5. Ranking generation based on accumulated ratings
    """
    # Setup: Create a minimal site with posts to evaluate
    site_root = tmp_path / "reader_site"
    posts_dir = site_root / "posts"
    posts_dir.mkdir(parents=True)

    # Create posts with varying content quality
    (posts_dir / "post1.md").write_text("# Post 1\nContent A", encoding="utf-8")
    (posts_dir / "post2.md").write_text("# Post 2\nContent B", encoding="utf-8")
    (posts_dir / "post3.md").write_text("# Post 3\nContent C", encoding="utf-8")

    # Configure Reader Agent with minimal comparisons for fast testing
    config = ReaderSettings(
        enabled=True,
        comparisons_per_post=1,
        k_factor=32,
        database_path=".egregora/reader.duckdb",
    )

    # Mock the AI comparison to avoid Gemini API calls
    # In production, this would use an LLM to judge which post is better
    with patch("egregora.agents.reader.reader_runner.compare_posts") as mock_compare:

        def deterministic_comparison(request, **kwargs):
            """Simulate AI judgment: post in position 'a' always wins."""
            return PostComparison(
                post_a_slug=request.post_a_slug,
                post_b_slug=request.post_b_slug,
                winner="a",
                reasoning="Post A has more detailed content.",
                feedback_a=ReaderFeedback(
                    comment="Well structured and informative",
                    star_rating=5,
                    engagement_level="high",
                ),
                feedback_b=ReaderFeedback(
                    comment="Could use more detail",
                    star_rating=3,
                    engagement_level="medium",
                ),
            )

        mock_compare.side_effect = deterministic_comparison

        # Execute the evaluation pipeline
        rankings = await run_reader_evaluation(posts_dir=posts_dir, config=config)

    # Verify: Rankings were generated
    assert len(rankings) > 0, "Reader Agent should produce rankings"

    # Verify: Database was created and persisted
    db_path = site_root / ".egregora" / "reader.duckdb"
    assert db_path.exists(), "ELO database should be persisted to disk"

    # Verify: Ratings reflect the comparison outcomes
    with DuckDBStorageManager(db_path=db_path) as storage:
        store = EloStore(storage)

        # Check that ratings were updated from default (1500)
        top_posts = store.get_top_posts(limit=10).execute()
        assert len(top_posts) > 0, "Should have rated posts"

        # The winning post should have rating above baseline
        top_rating = top_posts.iloc[0]["rating"]
        assert top_rating > 1500, f"Winner should have rating > 1500, got {top_rating}"

        # Verify wins were recorded
        top_wins = top_posts.iloc[0]["wins"]
        assert top_wins >= 1, f"Winner should have at least 1 win, got {top_wins}"

        # Verify comparison history is tracked (for auditing and analysis)
        history = store.get_comparison_history().execute()
        assert len(history) > 0, "Comparison history should be recorded"


# =============================================================================
# Eleventy Arrow Adapter: High-Performance Output Storage
# =============================================================================


def test_eleventy_adapter_buffers_documents_and_writes_parquet_per_window(tmp_path: Path) -> None:
    """Validate Eleventy Arrow adapter's document buffering and Parquet output.

    Why this matters:
    - Parquet storage enables efficient static site generation without intermediate files
    - Per-window batching allows incremental publishing (add new windows without rewrite)
    - Column-oriented storage enables fast filtering/sorting at build time
    - This is the high-performance alternative to markdown file output

    What we test:
    1. Document buffering by window label
    2. Parquet file creation per window
    3. Correct schema in Parquet files (id, slug, kind, body_md, etc.)
    4. Document retrieval by type and identifier
    5. Multiple document types (posts, profiles) in same window
    """
    # Setup: Initialize the adapter
    site_root = tmp_path / "eleventy_site"
    adapter = EleventyArrowAdapter(site_root=site_root, url_context=None)

    now = datetime.now(UTC)

    # Create documents for two different time windows
    # Window 1: A post and a profile (demonstrates mixed document types)
    post_1 = Document(
        content="# Post 1\n\nThis is the first post.",
        type=DocumentType.POST,
        metadata={"slug": "p1", "title": "First Post"},
        source_window="2025-01-01",
        created_at=now,
    )
    profile_1 = Document(
        content="Author bio for user 1",
        type=DocumentType.PROFILE,
        metadata={"uuid": "u1"},
        source_window="2025-01-01",
        created_at=now,
    )

    # Window 2: Another post (demonstrates incremental publishing)
    post_2 = Document(
        content="# Post 2\n\nThis is the second post.",
        type=DocumentType.POST,
        metadata={"slug": "p2", "title": "Second Post"},
        source_window="2025-01-02",
        created_at=now,
    )

    # Buffer documents (simulates pipeline output during window processing)
    adapter.serve(post_1)
    adapter.serve(profile_1)
    adapter.serve(post_2)

    # Finalize windows (triggers Parquet write)
    metadata1 = adapter.prepare_window("2025-01-01")
    adapter.finalize_window("2025-01-01", [], [], metadata1)

    metadata2 = adapter.prepare_window("2025-01-02")
    adapter.finalize_window("2025-01-02", [], [], metadata2)

    # Verify: Parquet files were created
    data_dir = site_root / "data"
    assert data_dir.exists(), "Data directory should be created"

    parquet_files = sorted(data_dir.glob("*.parquet"))
    assert len(parquet_files) == 2, "Should have one Parquet file per window"

    # Verify: Window 1 contains post and profile
    df_window_1 = pd.read_parquet(parquet_files[0])
    assert len(df_window_1) == 2, "Window 1 should have 2 documents"
    assert "p1" in df_window_1[df_window_1["kind"] == "post"]["slug"].to_numpy()

    profile_rows = df_window_1[df_window_1["kind"] == "profile"]
    assert len(profile_rows) == 1, "Should have 1 profile"
    assert "u1" in str(profile_rows["metadata"].to_numpy())

    # Verify: Window 2 contains second post
    df_window_2 = pd.read_parquet(parquet_files[1])
    assert len(df_window_2) == 1, "Window 2 should have 1 document"
    assert df_window_2.iloc[0]["slug"] == "p2"

    # Verify: Documents can be retrieved by type and identifier
    retrieved_post_1 = adapter.read_document(DocumentType.POST, "p1")
    assert retrieved_post_1 is not None, "Should find post p1"
    assert "first post" in retrieved_post_1.content.lower()

    retrieved_post_2 = adapter.read_document(DocumentType.POST, "p2")
    assert retrieved_post_2 is not None, "Should find post p2"
    assert "second post" in retrieved_post_2.content.lower()

    # Verify: Missing documents return None (not error)
    missing = adapter.read_document(DocumentType.POST, "nonexistent")
    assert missing is None, "Missing documents should return None"
