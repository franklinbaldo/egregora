from __future__ import annotations

import asyncio
import inspect
import json
import logging
from itertools import combinations
from pathlib import Path
from typing import Any

from egregora.agents.reader.compare import compare_posts
from egregora.agents.reader.elo import calculate_elo
from egregora.agents.reader.models import EvaluationRequest, PostComparison
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.elo_store import EloStore

logger = logging.getLogger(__name__)


async def _run_comparison(request: EvaluationRequest) -> PostComparison:
    """Call the comparison helper and normalize sync/async implementations."""

    result = compare_posts(request)
    if inspect.isawaitable(result):
        return await result
    return result  # type: ignore[return-value]


async def run_reader_evaluation(posts_dir: Path, config: Any) -> list[dict[str, Any]]:
    """Evaluate posts within a directory and return rankings.

    The implementation keeps the logic intentionally small for the test suite:
    - Pairwise comparisons are generated using simple combinations
    - Results are persisted via :class:`EloStore`
    - Rankings are returned as a list of dictionaries for convenience
    """

    posts = sorted(posts_dir.glob("*.md"))
    if len(posts) < 2:
        logger.info("Not enough posts to compare; skipping reader evaluation")
        return []

    site_root = posts_dir.parent
    db_dir = site_root / ".egregora"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "reader.duckdb"

    comparisons_per_post = getattr(config, "comparisons_per_post", 1)

    with DuckDBStorageManager(db_path=db_path) as storage:
        store = EloStore(storage)

        pairs = list(combinations(posts, 2))
        max_comparisons = max(1, comparisons_per_post)
        selected_pairs = pairs[: max_comparisons * len(posts)]

        for post_a, post_b in selected_pairs:
            request = EvaluationRequest(
                post_a_slug=post_a.stem,
                post_b_slug=post_b.stem,
                post_a_content=post_a.read_text(encoding="utf-8"),
                post_b_content=post_b.read_text(encoding="utf-8"),
            )

            comparison = await _run_comparison(request)
            rating_a = store.get_rating(request.post_a_slug)
            rating_b = store.get_rating(request.post_b_slug)

            new_a, new_b = calculate_elo(rating_a.rating, rating_b.rating, comparison.winner)
            store.update_ratings(
                post_a_slug=request.post_a_slug,
                post_b_slug=request.post_b_slug,
                rating_a_new=new_a,
                rating_b_new=new_b,
                winner=comparison.winner,
                comparison_id=f"{request.post_a_slug}-vs-{request.post_b_slug}",
                reader_feedback=json.dumps(comparison.model_dump()),
            )

        rankings = store.get_top_posts(limit=len(posts)).execute()
        return rankings.to_dict(orient="records")
