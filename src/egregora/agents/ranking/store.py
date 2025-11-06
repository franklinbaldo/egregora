"""DuckDB-backed ranking store for efficient updates and queries."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import duckdb
import ibis
import ibis.expr.datatypes as dt
from ibis.expr.types import Table

logger = logging.getLogger(__name__)


class RankingStore:
    """Ranking store using DuckDB with optional Parquet exports.

    Uses persistent DuckDB database for fast updates and ACID transactions.
    Can export to Parquet for sharing and external analytics.

    Follows the same pattern as VectorStore (rag/store.py).
    """

    def __init__(self, rankings_dir: Path) -> None:
        """Initialize ranking store.

        Args:
            rankings_dir: Directory for ranking data (e.g., site_root/rankings/)

        """
        self.rankings_dir = rankings_dir
        rankings_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = rankings_dir / "rankings.duckdb"
        self.conn = duckdb.connect(str(self.db_path))
        self._init_schema()
        logger.info("Ranking store initialized: %s", self.db_path)

    def _init_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        self.conn.execute(
            "\n            CREATE TABLE IF NOT EXISTS elo_ratings (\n                post_id VARCHAR PRIMARY KEY,\n                elo_global DOUBLE NOT NULL DEFAULT 1500,\n                games_played INTEGER NOT NULL DEFAULT 0,\n                last_updated TIMESTAMP NOT NULL\n            )\n        "
        )
        self.conn.execute(
            "\n            CREATE TABLE IF NOT EXISTS elo_history (\n                comparison_id VARCHAR PRIMARY KEY,\n                timestamp TIMESTAMP NOT NULL,\n                profile_id VARCHAR NOT NULL,\n                post_a VARCHAR NOT NULL,\n                post_b VARCHAR NOT NULL,\n                winner VARCHAR NOT NULL CHECK (winner IN ('A', 'B')),\n                comment_a VARCHAR NOT NULL,\n                stars_a INTEGER NOT NULL CHECK (stars_a BETWEEN 1 AND 5),\n                comment_b VARCHAR NOT NULL,\n                stars_b INTEGER NOT NULL CHECK (stars_b BETWEEN 1 AND 5)\n            )\n        "
        )
        self.conn.execute(
            "\n            CREATE INDEX IF NOT EXISTS idx_history_post_a ON elo_history(post_a)\n        "
        )
        self.conn.execute(
            "\n            CREATE INDEX IF NOT EXISTS idx_history_post_b ON elo_history(post_b)\n        "
        )
        self.conn.execute(
            "\n            CREATE INDEX IF NOT EXISTS idx_history_timestamp ON elo_history(timestamp)\n        "
        )
        self.conn.execute(
            "\n            CREATE INDEX IF NOT EXISTS idx_ratings_games ON elo_ratings(games_played)\n        "
        )
        self.conn.execute(
            "\n            CREATE INDEX IF NOT EXISTS idx_ratings_elo ON elo_ratings(elo_global)\n        "
        )

    def initialize_ratings(self, post_ids: list[str]) -> int:
        """Initialize ratings for new posts.

        Only inserts posts that don't already exist (idempotent).

        Args:
            post_ids: List of post IDs (filename stems)

        Returns:
            Number of new posts initialized

        """
        if not post_ids:
            return 0
        now = datetime.now(UTC)
        result = self.conn.execute(
            "\n            INSERT INTO elo_ratings (post_id, elo_global, games_played, last_updated)\n            SELECT np.post_id, 1500, 0, ?\n            FROM (\n                SELECT DISTINCT unnest(?::VARCHAR[]) as post_id\n            ) AS np\n            WHERE NOT EXISTS (\n                SELECT 1 FROM elo_ratings er\n                WHERE er.post_id = np.post_id\n            )\n            RETURNING post_id\n        ",
            [now, post_ids],
        )
        inserted = len(result.fetchall())
        if inserted > 0:
            logger.info("Initialized %s new posts with default ELO 1500", inserted)
        return inserted

    def get_rating(self, post_id: str) -> dict[str, Any] | None:
        """Get rating for a specific post.

        Args:
            post_id: Post ID

        Returns:
            dict with elo_global and games_played, or None if not found

        """
        result = self.conn.execute(
            "\n            SELECT elo_global, games_played FROM elo_ratings WHERE post_id = ?\n        ",
            [post_id],
        ).fetchone()
        if result is not None:
            return {"elo_global": result[0], "games_played": result[1]}
        return None

    def update_ratings(
        self, post_a: str, post_b: str, new_elo_a: float, new_elo_b: float
    ) -> tuple[float, float]:
        """Update ELO ratings after a comparison.

        Args:
            post_a: First post ID
            post_b: Second post ID
            new_elo_a: New ELO rating for post A
            new_elo_b: New ELO rating for post B

        Returns:
            (new_elo_a, new_elo_b)

        """
        now = datetime.now(UTC)
        self.conn.execute(
            "\n            UPDATE elo_ratings\n            SET\n                elo_global = CASE\n                    WHEN post_id = ? THEN ?\n                    WHEN post_id = ? THEN ?\n                    ELSE elo_global\n                END,\n                games_played = games_played + CASE\n                    WHEN post_id IN (?, ?) THEN 1\n                    ELSE 0\n                END,\n                last_updated = CASE\n                    WHEN post_id IN (?, ?) THEN ?\n                    ELSE last_updated\n                END\n            WHERE post_id IN (?, ?)\n        ",
            [post_a, new_elo_a, post_b, new_elo_b, post_a, post_b, post_a, post_b, now, post_a, post_b],
        )
        logger.debug("Updated ratings: %s=%s, %s=%s", post_a, new_elo_a, post_b, new_elo_b)
        return (new_elo_a, new_elo_b)

    def save_comparison(self, comparison_data: dict[str, Any]) -> None:
        """Save comparison to history.

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
        self.conn.execute(
            "\n            INSERT INTO elo_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ",
            [
                comparison_data["comparison_id"],
                comparison_data["timestamp"],
                comparison_data["profile_id"],
                comparison_data["post_a"],
                comparison_data["post_b"],
                comparison_data["winner"],
                comparison_data["comment_a"],
                comparison_data["stars_a"],
                comparison_data["comment_b"],
                comparison_data["stars_b"],
            ],
        )
        logger.debug("Saved comparison %s", comparison_data["comparison_id"])

    def get_posts_to_compare(self, strategy: str = "fewest_games", n: int = 2) -> list[str]:
        """Select posts to compare based on strategy.

        Args:
            strategy: Selection strategy (currently only "fewest_games")
            n: Number of posts to return

        Returns:
            List of post IDs

        """
        if strategy == "fewest_games":
            result = self.conn.execute(
                "\n                SELECT post_id FROM elo_ratings\n                ORDER BY games_played ASC, RANDOM()\n                LIMIT ?\n            ",
                [n],
            ).fetchall()
            return [row[0] for row in result]
        msg = f"Unknown strategy: {strategy}"
        raise ValueError(msg)

    def get_comments_for_post(self, post_id: str) -> Table:
        """Get all comments for a specific post.

        Args:
            post_id: Post ID

        Returns:
            Ibis Table with columns: profile_id, timestamp, comment, stars

        """
        result = self.conn.execute(
            "\n            SELECT\n                profile_id,\n                timestamp,\n                CASE WHEN post_a = ? THEN comment_a ELSE comment_b END as comment,\n                CASE WHEN post_a = ? THEN stars_a ELSE stars_b END as stars\n            FROM elo_history\n            WHERE post_a = ? OR post_b = ?\n            ORDER BY timestamp\n        ",
            [post_id, post_id, post_id, post_id],
        ).fetchall()
        if not result:
            return ibis.memtable(
                [],
                schema=ibis.schema(
                    {
                        "profile_id": dt.string,
                        "timestamp": dt.Timestamp(timezone=None),
                        "comment": dt.string,
                        "stars": dt.int64,
                    }
                ),
            )
        rows = [{"profile_id": r[0], "timestamp": r[1], "comment": r[2], "stars": r[3]} for r in result]
        return ibis.memtable(rows)

    def get_top_posts(self, n: int = 10, min_games: int = 5) -> Table:
        """Get top-rated posts.

        Args:
            n: Number of posts to return
            min_games: Minimum number of games for confidence

        Returns:
            Ibis Table with post_id, elo_global, games_played, last_updated

        """
        cursor = self.conn.execute(
            "\n            SELECT * FROM elo_ratings\n            WHERE games_played >= ?\n            ORDER BY elo_global DESC\n            LIMIT ?\n        ",
            [min_games, n],
        )
        return self._rows_to_memtable(cursor)

    def get_all_ratings(self) -> Table:
        """Get all ratings as Ibis Table.

        Returns:
            Ibis Table with all elo_ratings data

        """
        cursor = self.conn.execute("SELECT * FROM elo_ratings ORDER BY elo_global DESC")
        return self._rows_to_memtable(cursor)

    def get_all_history(self) -> Table:
        """Get all comparison history as Ibis Table.

        Returns:
            Ibis Table with all elo_history data

        """
        cursor = self.conn.execute("SELECT * FROM elo_history ORDER BY timestamp")
        return self._rows_to_memtable(cursor)

    def _rows_to_memtable(self, cursor: duckdb.DuckDBPyConnection) -> Table:
        """Convert a DuckDB cursor result into an Ibis memtable."""
        description = cursor.description or []
        columns = [column[0] for column in description]
        rows = cursor.fetchall()
        if not columns:
            return ibis.memtable([])
        records = [dict(zip(columns, row, strict=False)) for row in rows]
        return ibis.memtable(records)

    def export_to_parquet(self) -> None:
        """Export DuckDB tables to Parquet for sharing/analytics.

        Creates:
            - rankings/elo_ratings.parquet
            - rankings/elo_history.parquet
        """
        ratings_path = self.rankings_dir / "elo_ratings.parquet"
        history_path = self.rankings_dir / "elo_history.parquet"
        self.conn.execute(f"\n            COPY elo_ratings TO '{ratings_path}' (FORMAT PARQUET)\n        ")
        self.conn.execute(f"\n            COPY elo_history TO '{history_path}' (FORMAT PARQUET)\n        ")
        logger.info("Exported rankings to Parquet: %s", self.rankings_dir)

    def stats(self) -> dict[str, Any]:
        """Get ranking store statistics.

        Returns:
            dict with stats about ratings and history

        """
        ratings_count_result = self.conn.execute("SELECT COUNT(*) FROM elo_ratings").fetchone()
        ratings_count = ratings_count_result[0] if ratings_count_result is not None else 0
        comparisons_count_result = self.conn.execute("SELECT COUNT(*) FROM elo_history").fetchone()
        comparisons_count = comparisons_count_result[0] if comparisons_count_result is not None else 0
        avg_games_result = self.conn.execute(
            "\n            SELECT AVG(games_played) FROM elo_ratings\n        "
        ).fetchone()
        avg_games = (avg_games_result[0] if avg_games_result is not None else 0) or 0
        top_elo_result = self.conn.execute(
            "\n            SELECT MAX(elo_global) FROM elo_ratings\n        "
        ).fetchone()
        top_elo = (top_elo_result[0] if top_elo_result is not None else 1500) or 1500
        bottom_elo_result = self.conn.execute(
            "\n            SELECT MIN(elo_global) FROM elo_ratings\n        "
        ).fetchone()
        bottom_elo = (bottom_elo_result[0] if bottom_elo_result is not None else 1500) or 1500
        return {
            "total_posts": ratings_count,
            "total_comparisons": comparisons_count,
            "avg_games_per_post": avg_games,
            "highest_elo": top_elo,
            "lowest_elo": bottom_elo,
        }
