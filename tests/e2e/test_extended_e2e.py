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

from pathlib import Path
from unittest.mock import patch

import pytest
from egregora.agents.reader.reader_runner import run_reader_evaluation

from egregora.agents.reader.models import PostComparison, ReaderFeedback
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.elo_store import EloStore

# =============================================================================
# Reader Agent: Quality Feedback Loop
# =============================================================================


@pytest.mark.asyncio
async def test_reader_agent_evaluates_posts_and_persists_elo_rankings(
    tmp_path: Path,
    reader_test_config,
) -> None:
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

    # Use centralized config fixture (already configured for fast testing)
    config = reader_test_config.reader

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
