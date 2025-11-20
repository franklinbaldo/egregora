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
from ibis import _

from egregora.agents.reader.elo import DEFAULT_ELO
from egregora.database.duckdb_manager import DuckDBStorageManager

if TYPE_CHECKING:
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)

# Schema for ELO ratings table
ELO_RATINGS_SCHEMA = ibis.schema(
    {
        "post_slug": "string",
        "rating": "float64",
        "comparisons": "int64",
        "wins": "int64",
        "losses": "int64",
        "ties": "int64",
        "last_updated": "timestamp",
        "created_at": "timestamp",
    }
)

# Schema for comparison history
COMPARISON_HISTORY_SCHEMA = ibis.schema(
    {
        "comparison_id": "string",
        "post_a_slug": "string",
        "post_b_slug": "string",
        "winner": "string",  # "a", "b", or "tie"
        "rating_a_before": "float64",
        "rating_b_before": "float64",
        "rating_a_after": "float64",
        "rating_b_after": "float64",
        "timestamp": "timestamp",
        "reader_feedback": "string",  # JSON string with comments/ratings
    }
)


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
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create ratings and history tables if they don't exist."""
        # Create ratings table
        if "elo_ratings" not in self.storage.ibis_conn.list_tables():
            self.storage.ibis_conn.create_table(
                "elo_ratings",
                schema=ELO_RATINGS_SCHEMA,
            )
            logger.info("Created elo_ratings table")

        # Create comparison history table
        if "comparison_history" not in self.storage.ibis_conn.list_tables():
            self.storage.ibis_conn.create_table(
                "comparison_history",
                schema=COMPARISON_HISTORY_SCHEMA,
            )
            logger.info("Created comparison_history table")

    def get_rating(self, post_slug: str) -> EloRating:
        """Get current ELO rating for a post.

        Args:
            post_slug: Post identifier

        Returns:
            EloRating with current stats, or new rating at DEFAULT_ELO

        """
        ratings_table = self.storage.ibis_conn.table("elo_ratings")
        result = ratings_table.filter(_.post_slug == post_slug).limit(1).execute()

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

    def update_ratings(  # noqa: PLR0913
        self,
        post_a_slug: str,
        post_b_slug: str,
        rating_a_new: float,
        rating_b_new: float,
        winner: str,
        comparison_id: str,
        reader_feedback: str | None = None,
    ) -> None:
        """Update ratings after a comparison.

        Args:
            post_a_slug: First post identifier
            post_b_slug: Second post identifier
            rating_a_new: New rating for post A
            rating_b_new: New rating for post B
            winner: Comparison result ("a", "b", or "tie")
            comparison_id: Unique identifier for this comparison
            reader_feedback: Optional JSON string with reader comments/ratings

        """
        # Get current ratings
        rating_a = self.get_rating(post_a_slug)
        rating_b = self.get_rating(post_b_slug)

        now = datetime.now(UTC)

        # Update post A
        self._upsert_rating(
            post_slug=post_a_slug,
            rating=rating_a_new,
            comparisons=rating_a.comparisons + 1,
            wins=rating_a.wins + (1 if winner == "a" else 0),
            losses=rating_a.losses + (1 if winner == "b" else 0),
            ties=rating_a.ties + (1 if winner == "tie" else 0),
            last_updated=now,
            created_at=rating_a.created_at,
        )

        # Update post B
        self._upsert_rating(
            post_slug=post_b_slug,
            rating=rating_b_new,
            comparisons=rating_b.comparisons + 1,
            wins=rating_b.wins + (1 if winner == "b" else 0),
            losses=rating_b.losses + (1 if winner == "a" else 0),
            ties=rating_b.ties + (1 if winner == "tie" else 0),
            last_updated=now,
            created_at=rating_b.created_at,
        )

        # Record comparison history
        self._record_comparison(
            comparison_id=comparison_id,
            post_a_slug=post_a_slug,
            post_b_slug=post_b_slug,
            winner=winner,
            rating_a_before=rating_a.rating,
            rating_b_before=rating_b.rating,
            rating_a_after=rating_a_new,
            rating_b_after=rating_b_new,
            timestamp=now,
            reader_feedback=reader_feedback,
        )

        logger.info(
            "Updated ratings: %s (%.1f → %.1f), %s (%.1f → %.1f)",
            post_a_slug,
            rating_a.rating,
            rating_a_new,
            post_b_slug,
            rating_b.rating,
            rating_b_new,
        )

    def _upsert_rating(  # noqa: PLR0913
        self,
        post_slug: str,
        rating: float,
        comparisons: int,
        wins: int,
        losses: int,
        ties: int,
        last_updated: datetime,
        created_at: datetime,
    ) -> None:
        """Insert or update a rating record."""
        # DuckDB doesn't support UPSERT directly in Ibis, so we delete + insert
        # Delete existing record
        self.storage.ibis_conn.raw_sql(
            "DELETE FROM elo_ratings WHERE post_slug = ?",
            parameters=[post_slug],
        )

        # Insert new record
        new_row = ibis.memtable(
            [
                {
                    "post_slug": post_slug,
                    "rating": rating,
                    "comparisons": comparisons,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "last_updated": last_updated,
                    "created_at": created_at,
                }
            ],
            schema=ELO_RATINGS_SCHEMA,
        )

        self.storage.ibis_conn.insert("elo_ratings", new_row)

    def _record_comparison(  # noqa: PLR0913
        self,
        comparison_id: str,
        post_a_slug: str,
        post_b_slug: str,
        winner: str,
        rating_a_before: float,
        rating_b_before: float,
        rating_a_after: float,
        rating_b_after: float,
        timestamp: datetime,
        reader_feedback: str | None,
    ) -> None:
        """Record a comparison in history."""
        new_comparison = ibis.memtable(
            [
                {
                    "comparison_id": comparison_id,
                    "post_a_slug": post_a_slug,
                    "post_b_slug": post_b_slug,
                    "winner": winner,
                    "rating_a_before": rating_a_before,
                    "rating_b_before": rating_b_before,
                    "rating_a_after": rating_a_after,
                    "rating_b_after": rating_b_after,
                    "timestamp": timestamp,
                    "reader_feedback": reader_feedback or "",
                }
            ],
            schema=COMPARISON_HISTORY_SCHEMA,
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
        return ratings_table.filter(_.comparisons > 0).order_by(_.rating.desc()).limit(limit)

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
        history_table = self.storage.ibis_conn.table("comparison_history")

        if post_slug:
            history_table = history_table.filter((_.post_a_slug == post_slug) | (_.post_b_slug == post_slug))

        history_table = history_table.order_by(_.timestamp.desc())

        if limit:
            history_table = history_table.limit(limit)

        return history_table
