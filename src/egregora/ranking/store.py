"""DuckDB-backed ranking store for efficient updates and queries."""

import logging
from pathlib import Path
from datetime import datetime, timezone
import duckdb
import polars as pl

logger = logging.getLogger(__name__)


class RankingStore:
    """
    Ranking store using DuckDB with optional Parquet exports.

    Uses persistent DuckDB database for fast updates and ACID transactions.
    Can export to Parquet for sharing and external analytics.

    Follows the same pattern as VectorStore (rag/store.py).
    """

    def __init__(self, rankings_dir: Path):
        """
        Initialize ranking store.

        Args:
            rankings_dir: Directory for ranking data (e.g., site_root/rankings/)
        """
        self.rankings_dir = rankings_dir
        rankings_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = rankings_dir / "rankings.duckdb"
        self.conn = duckdb.connect(str(self.db_path))
        self._init_schema()

        logger.info(f"Ranking store initialized: {self.db_path}")

    def _init_schema(self):
        """Create tables and indexes if they don't exist."""
        # ELO ratings table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS elo_ratings (
                post_id VARCHAR PRIMARY KEY,
                elo_global DOUBLE NOT NULL DEFAULT 1500,
                games_played INTEGER NOT NULL DEFAULT 0,
                last_updated TIMESTAMP NOT NULL
            )
        """)

        # Comparison history table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS elo_history (
                comparison_id VARCHAR PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                profile_id VARCHAR NOT NULL,
                post_a VARCHAR NOT NULL,
                post_b VARCHAR NOT NULL,
                winner VARCHAR NOT NULL CHECK (winner IN ('A', 'B')),
                comment_a VARCHAR NOT NULL,
                stars_a INTEGER NOT NULL CHECK (stars_a BETWEEN 1 AND 5),
                comment_b VARCHAR NOT NULL,
                stars_b INTEGER NOT NULL CHECK (stars_b BETWEEN 1 AND 5)
            )
        """)

        # Create indexes for efficient queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_post_a ON elo_history(post_a)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_post_b ON elo_history(post_b)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_timestamp ON elo_history(timestamp)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ratings_games ON elo_ratings(games_played)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ratings_elo ON elo_ratings(elo_global)
        """)

    def initialize_ratings(self, post_ids: list[str]) -> int:
        """
        Initialize ratings for new posts.

        Only inserts posts that don't already exist (idempotent).

        Args:
            post_ids: List of post IDs (filename stems)

        Returns:
            Number of new posts initialized
        """
        if not post_ids:
            return 0

        now = datetime.now(timezone.utc)
        inserted = 0

        for post_id in post_ids:
            result = self.conn.execute("""
                INSERT INTO elo_ratings (post_id, elo_global, games_played, last_updated)
                VALUES (?, 1500, 0, ?)
                ON CONFLICT (post_id) DO NOTHING
            """, [post_id, now])
            inserted += result.fetchone()[0]  # Returns number of rows inserted

        if inserted > 0:
            logger.info(f"Initialized {inserted} new posts with default ELO 1500")

        return inserted

    def get_rating(self, post_id: str) -> dict | None:
        """
        Get rating for a specific post.

        Args:
            post_id: Post ID

        Returns:
            dict with elo_global and games_played, or None if not found
        """
        result = self.conn.execute("""
            SELECT elo_global, games_played FROM elo_ratings WHERE post_id = ?
        """, [post_id]).fetchone()

        if result:
            return {'elo_global': result[0], 'games_played': result[1]}
        return None

    def update_ratings(
        self,
        post_a: str,
        post_b: str,
        new_elo_a: float,
        new_elo_b: float
    ) -> tuple[float, float]:
        """
        Update ELO ratings after a comparison.

        Args:
            post_a: First post ID
            post_b: Second post ID
            new_elo_a: New ELO rating for post A
            new_elo_b: New ELO rating for post B

        Returns:
            (new_elo_a, new_elo_b)
        """
        now = datetime.now(timezone.utc)

        self.conn.execute("""
            UPDATE elo_ratings
            SET elo_global = ?, games_played = games_played + 1, last_updated = ?
            WHERE post_id = ?
        """, [new_elo_a, now, post_a])

        self.conn.execute("""
            UPDATE elo_ratings
            SET elo_global = ?, games_played = games_played + 1, last_updated = ?
            WHERE post_id = ?
        """, [new_elo_b, now, post_b])

        logger.debug(f"Updated ratings: {post_a}={new_elo_a:.0f}, {post_b}={new_elo_b:.0f}")

        return new_elo_a, new_elo_b

    def save_comparison(self, comparison_data: dict):
        """
        Save comparison to history.

        Args:
            comparison_data: dict with keys:
                - comparison_id: str
                - timestamp: datetime
                - profile_id: str
                - post_a: str
                - post_b: str
                - winner: str ("A" or "B")
                - comment_a: str
                - stars_a: int
                - comment_b: str
                - stars_b: int
        """
        self.conn.execute("""
            INSERT INTO elo_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            comparison_data['comparison_id'],
            comparison_data['timestamp'],
            comparison_data['profile_id'],
            comparison_data['post_a'],
            comparison_data['post_b'],
            comparison_data['winner'],
            comparison_data['comment_a'],
            comparison_data['stars_a'],
            comparison_data['comment_b'],
            comparison_data['stars_b'],
        ])

        logger.debug(f"Saved comparison {comparison_data['comparison_id']}")

    def get_posts_to_compare(self, strategy: str = "fewest_games", n: int = 2) -> list[str]:
        """
        Select posts to compare based on strategy.

        Args:
            strategy: Selection strategy (currently only "fewest_games")
            n: Number of posts to return

        Returns:
            List of post IDs
        """
        if strategy == "fewest_games":
            result = self.conn.execute("""
                SELECT post_id FROM elo_ratings
                ORDER BY games_played ASC, RANDOM()
                LIMIT ?
            """, [n]).fetchall()
            return [row[0] for row in result]
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def get_comments_for_post(self, post_id: str) -> pl.DataFrame:
        """
        Get all comments for a specific post.

        Args:
            post_id: Post ID

        Returns:
            DataFrame with columns: profile_id, timestamp, comment, stars
        """
        result = self.conn.execute("""
            SELECT
                profile_id,
                timestamp,
                CASE WHEN post_a = ? THEN comment_a ELSE comment_b END as comment,
                CASE WHEN post_a = ? THEN stars_a ELSE stars_b END as stars
            FROM elo_history
            WHERE post_a = ? OR post_b = ?
            ORDER BY timestamp
        """, [post_id, post_id, post_id, post_id]).arrow()

        return pl.from_arrow(result)

    def get_top_posts(self, n: int = 10, min_games: int = 5) -> pl.DataFrame:
        """
        Get top-rated posts.

        Args:
            n: Number of posts to return
            min_games: Minimum number of games for confidence

        Returns:
            DataFrame with post_id, elo_global, games_played, last_updated
        """
        result = self.conn.execute("""
            SELECT * FROM elo_ratings
            WHERE games_played >= ?
            ORDER BY elo_global DESC
            LIMIT ?
        """, [min_games, n]).arrow()

        return pl.from_arrow(result)

    def get_all_ratings(self) -> pl.DataFrame:
        """
        Get all ratings as DataFrame.

        Returns:
            DataFrame with all elo_ratings data
        """
        result = self.conn.execute("SELECT * FROM elo_ratings ORDER BY elo_global DESC").arrow()
        return pl.from_arrow(result)

    def get_all_history(self) -> pl.DataFrame:
        """
        Get all comparison history as DataFrame.

        Returns:
            DataFrame with all elo_history data
        """
        result = self.conn.execute("SELECT * FROM elo_history ORDER BY timestamp").arrow()
        return pl.from_arrow(result)

    def export_to_parquet(self):
        """
        Export DuckDB tables to Parquet for sharing/analytics.

        Creates:
            - rankings/elo_ratings.parquet
            - rankings/elo_history.parquet
        """
        ratings_path = self.rankings_dir / "elo_ratings.parquet"
        history_path = self.rankings_dir / "elo_history.parquet"

        self.conn.execute(f"""
            COPY elo_ratings TO '{ratings_path}' (FORMAT PARQUET)
        """)
        self.conn.execute(f"""
            COPY elo_history TO '{history_path}' (FORMAT PARQUET)
        """)

        logger.info(f"Exported rankings to Parquet: {self.rankings_dir}")

    def stats(self) -> dict:
        """
        Get ranking store statistics.

        Returns:
            dict with stats about ratings and history
        """
        ratings_count = self.conn.execute("SELECT COUNT(*) FROM elo_ratings").fetchone()[0]
        comparisons_count = self.conn.execute("SELECT COUNT(*) FROM elo_history").fetchone()[0]

        avg_games = self.conn.execute("""
            SELECT AVG(games_played) FROM elo_ratings
        """).fetchone()[0] or 0

        top_elo = self.conn.execute("""
            SELECT MAX(elo_global) FROM elo_ratings
        """).fetchone()[0] or 1500

        bottom_elo = self.conn.execute("""
            SELECT MIN(elo_global) FROM elo_ratings
        """).fetchone()[0] or 1500

        return {
            "total_posts": ratings_count,
            "total_comparisons": comparisons_count,
            "avg_games_per_post": avg_games,
            "highest_elo": top_elo,
            "lowest_elo": bottom_elo,
        }
