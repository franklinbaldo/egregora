"""Orchestration helpers for the reader agent evaluation loop."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from egregora.agents.reader.agent import compare_posts
from egregora.agents.reader.elo import calculate_elo_update
from egregora.agents.reader.models import EvaluationRequest, RankingResult
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.text import slugify
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.elo_store import EloStore
from egregora.database.init import initialize_database

if TYPE_CHECKING:
    from egregora.config.settings import ReaderSettings

logger = logging.getLogger(__name__)
MIN_POSTS_FOR_COMPARISON = 2


def select_post_pairs(
    post_slugs: list[str],
    comparisons_per_post: int,
    elo_store: EloStore,
) -> list[tuple[str, str]]:
    """Select balanced post pairs for reader comparisons."""
    if len(post_slugs) < MIN_POSTS_FOR_COMPARISON:
        logger.warning("Need at least 2 posts for reader comparisons")
        return []

    ratings: list[tuple[str, float, int]] = []
    for slug in post_slugs:
        rating = elo_store.get_rating(slug)
        ratings.append((slug, rating.rating, rating.comparisons))

    ratings.sort(key=lambda item: item[1], reverse=True)

    pairs: list[tuple[str, str]] = []
    for i in range(len(ratings)):
        for offset in range(1, min(comparisons_per_post + 1, len(ratings))):
            j = (i + offset) % len(ratings)
            if i < j:
                pairs.append((ratings[i][0], ratings[j][0]))

    logger.info(
        "Selected %d post pairs from %d posts (target %d comparisons/post)",
        len(pairs),
        len(post_slugs),
        comparisons_per_post,
    )
    return pairs


def run_reader_evaluation(
    posts_dir: Path,
    config: ReaderSettings,
    model: str | None = None,
) -> list[RankingResult]:
    """Evaluate posts with the reader agent and persist ELO rankings."""
    if not config.enabled:
        logger.info("Reader agent disabled in config")
        return []

    posts_dir = posts_dir.expanduser().resolve()
    if not posts_dir.exists():
        logger.warning("Posts directory not found: %s", posts_dir)
        return []

    db_path = Path(config.database_path)
    if not db_path.is_absolute():
        db_path = posts_dir.parent / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    post_files = sorted(posts_dir.glob("**/*.md"))
    if not post_files:
        logger.warning("No posts found for evaluation")
        return []

    slug_documents: dict[str, Document] = {}
    for file_path in post_files:
        slug_value = slugify(file_path.stem) or file_path.stem
        content = file_path.read_text(encoding="utf-8")
        slug_documents[slug_value] = Document(
            content=content,
            type=DocumentType.POST,
            metadata={"slug": slug_value},
        )

    post_slugs = list(slug_documents.keys())
    if len(post_slugs) < MIN_POSTS_FOR_COMPARISON:
        logger.warning("Need at least 2 unique slugs for reader evaluation")
        return []

    with DuckDBStorageManager(db_path=db_path) as storage:
        initialize_database(storage.ibis_conn)
        elo_store = EloStore(storage)

        pairs = select_post_pairs(post_slugs, config.comparisons_per_post, elo_store)
        if not pairs:
            logger.warning("No post pairs selected for comparison")
            return []

        for idx, (slug_a, slug_b) in enumerate(pairs, start=1):
            document_a = slug_documents[slug_a]
            document_b = slug_documents[slug_b]

            request = EvaluationRequest(post_a=document_a, post_b=document_b)
            comparison = compare_posts(request, model=model)

            rating_a = elo_store.get_rating(slug_a)
            rating_b = elo_store.get_rating(slug_b)

            new_rating_a, new_rating_b = calculate_elo_update(
                rating_a.rating,
                rating_b.rating,
                comparison.winner,
                k_factor=config.k_factor,
            )

            feedback_payload = {
                "reasoning": comparison.reasoning,
                "feedback_a": {
                    "comment": comparison.feedback_a.comment,
                    "star_rating": comparison.feedback_a.star_rating,
                    "engagement_level": comparison.feedback_a.engagement_level,
                },
                "feedback_b": {
                    "comment": comparison.feedback_b.comment,
                    "star_rating": comparison.feedback_b.star_rating,
                    "engagement_level": comparison.feedback_b.engagement_level,
                },
            }

            elo_store.update_ratings(
                EloStore.UpdateParams(
                    post_a_slug=slug_a,
                    post_b_slug=slug_b,
                    rating_a_new=new_rating_a,
                    rating_b_new=new_rating_b,
                    winner=comparison.winner,
                    comparison_id=str(uuid.uuid4()),
                    reader_feedback=json.dumps(feedback_payload),
                )
            )

            logger.info(
                "Rank comparison %d/%d: %s vs %s -> winner %s",
                idx,
                len(pairs),
                slug_a,
                slug_b,
                comparison.winner,
            )

        top_posts = elo_store.get_top_posts(limit=len(post_slugs)).execute()

    rankings: list[RankingResult] = []
    for rank, row in enumerate(top_posts.itertuples(index=False), start=1):
        comparisons = int(row.comparisons)
        win_rate = (row.wins / comparisons * 100) if comparisons > 0 else 0.0
        rankings.append(
            RankingResult(
                post_slug=row.post_slug,
                rating=float(row.rating),
                rank=rank,
                comparisons=comparisons,
                win_rate=win_rate,
            )
        )

    return rankings
