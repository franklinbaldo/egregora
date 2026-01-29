"""Persistence layer for ELO ratings using DuckDB.

Stores post quality ratings with history tracking for:
- Current ratings
- Rating evolution over time
- Comparison metadata
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import ibis

from egregora.database.elo_record import ComparisonRecord
from egregora.database.schemas import ELO_HISTORY_SCHEMA, ELO_RATINGS_SCHEMA

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.database.duckdb_manager import DuckDBStorageManager

logger = logging.getLogger(__name__)

# Default rating assigned to posts without prior comparisons
DEFAULT_ELO = 1500.0


@dataclass(frozen=True, slots=True)
class EloRating:
    """Current ELO rating for a post."""

    post_slug: str
    rating: float
    comparisons: int
    wins: int
    losses: int
    ties: int
    last_updated: datetime
    created_at: datetime


class EloStore:
    """Persistent storage for ELO ratings using DuckDB."""

    def __init__(self, storage: DuckDBStorageManager) -> None:
        """Initialize ELO store.

        Args:
            storage: The central DuckDB storage manager.

        """
        self.storage = storage

    def get_rating(self, post_slug: str) -> EloRating:
        """Get current ELO rating for a post.

        Args:
            post_slug: Post identifier

        Returns:
            EloRating with current stats, or new rating at DEFAULT_ELO

        """
        ratings_table = self.storage.read_table("elo_ratings")
        result = ratings_table.filter(ratings_table.post_slug == post_slug).limit(1).execute()

        if result.empty:
            # Return default rating for new posts
            now = datetime.now(UTC)
            return EloRating(
                post_slug=post_slug,
                rating=DEFAULT_ELO,
                comparisons=0,
                wins=0,
                losses=0,
                ties=0,
                last_updated=now,
                created_at=now,
            )

        row = result.iloc[0]
        return EloRating(
            post_slug=row["post_slug"],
            rating=float(row["rating"]),
            comparisons=int(row["comparisons"]),
            wins=int(row["wins"]),
            losses=int(row["losses"]),
            ties=int(row["ties"]),
            last_updated=row["last_updated"],
            created_at=row["created_at"],
        )

    @dataclass
    class UpdateParams:
        """Parameters for updating ratings."""

        post_a_slug: str
        post_b_slug: str
        rating_a_new: float
        rating_b_new: float
        winner: str
        comparison_id: str
        reader_feedback: str | None = None

    def update_ratings(self, params: UpdateParams) -> None:
        """Update ratings after a comparison.

        Args:
            params: Update parameters object

        """
        # Get current ratings
        rating_a = self.get_rating(params.post_a_slug)
        rating_b = self.get_rating(params.post_b_slug)

        now = datetime.now(UTC)

        # Update post A
        rating_a_data = EloRating(
            post_slug=params.post_a_slug,
            rating=params.rating_a_new,
            comparisons=rating_a.comparisons + 1,
            wins=rating_a.wins + (1 if params.winner == "a" else 0),
            losses=rating_a.losses + (1 if params.winner == "b" else 0),
            ties=rating_a.ties + (1 if params.winner == "tie" else 0),
            last_updated=now,
            created_at=rating_a.created_at,
        )
        self._upsert_rating(rating_a_data)

        # Update post B
        rating_b_data = EloRating(
            post_slug=params.post_b_slug,
            rating=params.rating_b_new,
            comparisons=rating_b.comparisons + 1,
            wins=rating_b.wins + (1 if params.winner == "b" else 0),
            losses=rating_b.losses + (1 if params.winner == "a" else 0),
            ties=rating_b.ties + (1 if params.winner == "tie" else 0),
            last_updated=now,
            created_at=rating_b.created_at,
        )
        self._upsert_rating(rating_b_data)

        # Record comparison history
        comparison_data = ComparisonRecord(
            comparison_id=params.comparison_id,
            post_a_slug=params.post_a_slug,
            post_b_slug=params.post_b_slug,
            winner=params.winner,
            rating_a_before=rating_a.rating,
            rating_b_before=rating_b.rating,
            rating_a_after=params.rating_a_new,
            rating_b_after=params.rating_b_new,
            timestamp=now,
            reader_feedback=params.reader_feedback,
        )
        self._record_comparison(comparison_data)

        logger.info(
            "Updated ratings: %s (%.1f → %.1f), %s (%.1f → %.1f)",
            params.post_a_slug,
            rating_a.rating,
            params.rating_a_new,
            params.post_b_slug,
            rating_b.rating,
            params.rating_b_new,
        )

    def _upsert_rating(self, rating_data: EloRating) -> None:
        """Insert or update a rating record."""
        new_row = ibis.memtable(
            [
                {
                    "post_slug": rating_data.post_slug,
                    "rating": rating_data.rating,
                    "comparisons": rating_data.comparisons,
                    "wins": rating_data.wins,
                    "losses": rating_data.losses,
                    "ties": rating_data.ties,
                    "last_updated": rating_data.last_updated,
                    "created_at": rating_data.created_at,
                }
            ],
            schema=ELO_RATINGS_SCHEMA,
        )

        self.storage.replace_rows(
            "elo_ratings",
            new_row,
            by_keys={"post_slug": rating_data.post_slug},
        )

    def _record_comparison(self, record: ComparisonRecord) -> None:
        """Record a comparison in history."""
        new_comparison = ibis.memtable(
            [
                {
                    "comparison_id": record.comparison_id,
                    "post_a_slug": record.post_a_slug,
                    "post_b_slug": record.post_b_slug,
                    "winner": record.winner,
                    "rating_a_before": record.rating_a_before,
                    "rating_b_before": record.rating_b_before,
                    "rating_a_after": record.rating_a_after,
                    "rating_b_after": record.rating_b_after,
                    "timestamp": record.timestamp,
                    "reader_feedback": record.reader_feedback or "",
                }
            ],
            schema=ELO_HISTORY_SCHEMA,
        )

        self.storage.ibis_conn.insert("comparison_history", new_comparison)

    def get_top_posts(self, limit: int = 10) -> Table:
        """Get top-rated posts.

        Args:
            limit: Maximum number of posts to return

        Returns:
            Ibis table with top posts sorted by rating

        """
        ratings_table = self.storage.ibis_conn.table("elo_ratings")
        return (
            ratings_table.filter(ratings_table.comparisons > 0)
            .order_by(ratings_table.rating.desc())
            .limit(limit)
        )

    def get_comparison_history(
        self,
        post_slug: str | None = None,
        limit: int | None = None,
    ) -> Table:
        """Get comparison history.

        Args:
            post_slug: Optional filter for specific post
            limit: Maximum number of comparisons to return

        Returns:
            Ibis table with comparison history

        """
        history_table = self.storage.read_table("comparison_history")

        if post_slug:
            history_table = history_table.filter(
                (history_table.post_a_slug == post_slug) | (history_table.post_b_slug == post_slug)
            )

        history_table = history_table.order_by(ibis.desc("timestamp"))

        if limit:
            history_table = history_table.limit(limit)

        return history_table
