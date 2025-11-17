"""Reader agent orchestration for post ranking and evaluation.

Coordinates post selection, comparison execution, and ELO rating updates.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from egregora.agents.reader.agent import compare_posts
from egregora.agents.reader.elo import calculate_elo_update
from egregora.agents.reader.models import EvaluationRequest, RankingResult
from egregora.database.elo_store import EloStore

if TYPE_CHECKING:
    from egregora.config.settings import ReaderSettings

logger = logging.getLogger(__name__)


def select_post_pairs(
    post_slugs: list[str],
    comparisons_per_post: int,
    elo_store: EloStore,
) -> list[tuple[str, str]]:
    """Select post pairs for comparison using rating-based matching.

    Pairs posts with similar ratings for balanced comparisons.

    Args:
        post_slugs: List of post identifiers
        comparisons_per_post: Target number of comparisons per post
        elo_store: ELO rating store

    Returns:
        List of (slug_a, slug_b) tuples to compare

    """
    if len(post_slugs) < 2:
        logger.warning("Need at least 2 posts for comparison, got %d", len(post_slugs))
        return []

    # Get current ratings for all posts
    ratings = []
    for slug in post_slugs:
        rating_data = elo_store.get_rating(slug)
        ratings.append((slug, rating_data.rating, rating_data.comparisons))

    # Sort by rating (highest first)
    ratings.sort(key=lambda x: x[1], reverse=True)

    # Simple pairing: match adjacent posts in rating order
    # This creates balanced matchups between similarly-rated posts
    pairs = []
    total_needed = (len(post_slugs) * comparisons_per_post) // 2

    # Round-robin pairing: each post gets compared to nearby posts
    for i in range(len(ratings)):
        for offset in range(1, min(comparisons_per_post + 1, len(ratings))):
            j = (i + offset) % len(ratings)
            if i < j:  # Avoid duplicates (A vs B is same as B vs A)
                pairs.append((ratings[i][0], ratings[j][0]))
                if len(pairs) >= total_needed:
                    break
        if len(pairs) >= total_needed:
            break

    logger.info(
        "Selected %d post pairs from %d posts (%d comparisons/post target)",
        len(pairs),
        len(post_slugs),
        comparisons_per_post,
    )

    return pairs


async def run_reader_evaluation(
    posts_dir: Path,
    config: ReaderSettings,
    model: str | None = None,
) -> list[RankingResult]:
    """Run reader agent evaluation on all posts in a directory.

    Args:
        posts_dir: Directory containing markdown posts
        config: Reader configuration
        model: Optional model override

    Returns:
        List of ranking results sorted by ELO rating

    Example:
        >>> from pathlib import Path
        >>> from egregora.config.settings import ReaderSettings
        >>> config = ReaderSettings(enabled=True, comparisons_per_post=5)
        >>> rankings = await run_reader_evaluation(
        ...     Path("output/posts"),
        ...     config,
        ... )
        >>> for result in rankings[:10]:  # Top 10
        ...     print(f"{result.rank}. {result.post_slug} (ELO: {result.rating:.0f})")

    """
    if not config.enabled:
        logger.info("Reader agent disabled in config")
        return []

    # Initialize ELO store
    db_path = posts_dir.parent / config.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    elo_store = EloStore(db_path)

    try:
        # Discover posts
        post_files = list(posts_dir.glob("**/*.md"))
        if not post_files:
            logger.warning("No posts found in %s", posts_dir)
            return []

        post_slugs = [p.stem for p in post_files]
        logger.info("Found %d posts for evaluation", len(post_slugs))

        # Select post pairs
        pairs = select_post_pairs(post_slugs, config.comparisons_per_post, elo_store)

        if not pairs:
            logger.warning("No post pairs selected for comparison")
            return []

        # Run comparisons
        for idx, (slug_a, slug_b) in enumerate(pairs, 1):
            logger.info(
                "Comparison %d/%d: %s vs %s",
                idx,
                len(pairs),
                slug_a,
                slug_b,
            )

            # Load post content
            file_a = next(posts_dir.glob(f"**/{slug_a}.md"))
            file_b = next(posts_dir.glob(f"**/{slug_b}.md"))

            content_a = file_a.read_text(encoding="utf-8")
            content_b = file_b.read_text(encoding="utf-8")

            # Create evaluation request
            request = EvaluationRequest(
                post_a_slug=slug_a,
                post_b_slug=slug_b,
                post_a_content=content_a,
                post_b_content=content_b,
            )

            # Run comparison
            comparison = await compare_posts(request, model=model)

            # Get current ratings
            rating_a = elo_store.get_rating(slug_a)
            rating_b = elo_store.get_rating(slug_b)

            # Calculate new ratings
            new_rating_a, new_rating_b = calculate_elo_update(
                rating_a.rating,
                rating_b.rating,
                comparison.winner,
                k_factor=config.k_factor,
            )

            # Store comparison result with feedback
            import json

            feedback_json = json.dumps(
                {
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
                    "reasoning": comparison.reasoning,
                }
            )

            # Update ratings
            elo_store.update_ratings(
                post_a_slug=slug_a,
                post_b_slug=slug_b,
                rating_a_new=new_rating_a,
                rating_b_new=new_rating_b,
                winner=comparison.winner,
                comparison_id=str(uuid.uuid4()),
                reader_feedback=feedback_json,
            )

            logger.info(
                "Updated ratings: %s %.0f→%.0f, %s %.0f→%.0f (winner: %s)",
                slug_a,
                rating_a.rating,
                new_rating_a,
                slug_b,
                rating_b.rating,
                new_rating_b,
                comparison.winner,
            )

        # Generate rankings
        top_posts = elo_store.get_top_posts(limit=len(post_slugs)).execute()

        rankings = []
        for rank, row in enumerate(top_posts.itertuples(index=False), 1):
            total_games = row.comparisons
            win_rate = (row.wins / total_games * 100) if total_games > 0 else 0.0

            rankings.append(
                RankingResult(
                    post_slug=row.post_slug,
                    rating=float(row.rating),
                    rank=rank,
                    comparisons=int(row.comparisons),
                    win_rate=win_rate,
                )
            )

        logger.info("Generated rankings for %d posts", len(rankings))
        return rankings

    finally:
        elo_store.close()
