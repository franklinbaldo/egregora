"""DuckDB-backed ranking store for efficient updates and queries."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict

import duckdb
import ibis
import ibis.expr.datatypes as dt
import pyarrow as pa
from ibis.expr.types import Table

from egregora.sql_templates import render_sql_template

logger = logging.getLogger(__name__)


ELO_RATINGS_TABLE = "elo_ratings"
ELO_HISTORY_TABLE = "elo_history"
ELO_HISTORY_POST_A_INDEX = "idx_history_post_a"
ELO_HISTORY_POST_B_INDEX = "idx_history_post_b"
ELO_HISTORY_TIMESTAMP_INDEX = "idx_history_timestamp"
ELO_RATINGS_GAMES_INDEX = "idx_ratings_games"
ELO_RATINGS_ELO_INDEX = "idx_ratings_elo"


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

    def _init_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        # ELO ratings table
        self.conn.execute(
            render_sql_template(
                "ranking_elo_ratings_table.sql.jinja",
                table_name=ELO_RATINGS_TABLE,
            )
        )

        # Comparison history table
        self.conn.execute(
            render_sql_template(
                "ranking_elo_history_table.sql.jinja",
                table_name=ELO_HISTORY_TABLE,
                ratings_table_name=ELO_RATINGS_TABLE,
            )
        )

        # Create indexes for efficient queries
        self.conn.execute(
            render_sql_template(
                "create_index.sql.jinja",
                index_name=ELO_HISTORY_POST_A_INDEX,
                table_name=ELO_HISTORY_TABLE,
                columns=["post_a"],
            )
        )
        self.conn.execute(
            render_sql_template(
                "create_index.sql.jinja",
                index_name=ELO_HISTORY_POST_B_INDEX,
                table_name=ELO_HISTORY_TABLE,
                columns=["post_b"],
            )
        )
        self.conn.execute(
            render_sql_template(
                "create_index.sql.jinja",
                index_name=ELO_HISTORY_TIMESTAMP_INDEX,
                table_name=ELO_HISTORY_TABLE,
                columns=["timestamp"],
            )
        )
        self.conn.execute(
            render_sql_template(
                "create_index.sql.jinja",
                index_name=ELO_RATINGS_GAMES_INDEX,
                table_name=ELO_RATINGS_TABLE,
                columns=["games_played"],
            )
        )
        self.conn.execute(
            render_sql_template(
                "create_index.sql.jinja",
                index_name=ELO_RATINGS_ELO_INDEX,
                table_name=ELO_RATINGS_TABLE,
                columns=["elo_global"],
            )
        )

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

        now = datetime.now(UTC)
        inserted = 0

        for post_id in post_ids:
            result = self.conn.execute(
                f"""
                INSERT INTO {ELO_RATINGS_TABLE} (post_id, elo_global, games_played, last_updated)
                VALUES (?, 1500, 0, ?)
                ON CONFLICT (post_id) DO NOTHING
            """,
                [post_id, now],
            ).fetchone()
            if result is not None:
                inserted += result[0]

        if inserted > 0:
            logger.info(f"Initialized {inserted} new posts with default ELO 1500")

        return inserted

    def get_rating(self, post_id: str) -> Dict[str, Any] | None:
        """
        Get rating for a specific post.

        Args:
            post_id: Post ID

        Returns:
            dict with elo_global and games_played, or None if not found
        """
        result = self.conn.execute(
            f"""
            SELECT elo_global, games_played FROM {ELO_RATINGS_TABLE} WHERE post_id = ?
        """,
            [post_id],
        ).fetchone()

        if result is not None:
            return {"elo_global": result[0], "games_played": result[1]}
        return None

    def update_ratings(
        self, post_a: str, post_b: str, new_elo_a: float, new_elo_b: float
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
        now = datetime.now(UTC)

        self.conn.execute(
            f"""
            UPDATE {ELO_RATINGS_TABLE}
            SET elo_global = ?, games_played = games_played + 1, last_updated = ?
            WHERE post_id = ?
        """,
            [new_elo_a, now, post_a],
        )

        self.conn.execute(
            f"""
            UPDATE {ELO_RATINGS_TABLE}
            SET elo_global = ?, games_played = games_played + 1, last_updated = ?
            WHERE post_id = ?
        """,
            [new_elo_b, now, post_b],
        )

        logger.debug(f"Updated ratings: {post_a}={new_elo_a:.0f}, {post_b}={new_elo_b:.0f}")

        return new_elo_a, new_elo_b

    def save_comparison(self, comparison_data: Dict[str, Any]) -> None:
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
        self.initialize_ratings(
            list({comparison_data["post_a"], comparison_data["post_b"]})
        )

        self.conn.execute(
            """
            INSERT INTO elo_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
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
            result = self.conn.execute(
                """
                SELECT post_id FROM elo_ratings
                ORDER BY games_played ASC, RANDOM()
                LIMIT ?
            """,
                [n],
            ).fetchall()
            return [row[0] for row in result]
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def get_comments_for_post(self, post_id: str) -> Table:
        """
        Get all comments for a specific post.

        Args:
            post_id: Post ID

        Returns:
            Ibis Table with columns: profile_id, timestamp, comment, stars
        """
        result = self.conn.execute(
            """
            SELECT
                profile_id,
                timestamp,
                CASE WHEN post_a = ? THEN comment_a ELSE comment_b END as comment,
                CASE WHEN post_a = ? THEN stars_a ELSE stars_b END as stars
            FROM elo_history
            WHERE post_a = ? OR post_b = ?
            ORDER BY timestamp
        """,
            [post_id, post_id, post_id, post_id],
        ).fetchall()

        # Convert to Ibis Table, handling empty results
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

        # Convert to list of dicts for Ibis
        rows = [
            {"profile_id": r[0], "timestamp": r[1], "comment": r[2], "stars": r[3]} for r in result
        ]
        return ibis.memtable(rows)

    def get_top_posts(self, n: int = 10, min_games: int = 5) -> Table:
        """
        Get top-rated posts.

        Args:
            n: Number of posts to return
            min_games: Minimum number of games for confidence

        Returns:
            Ibis Table with post_id, elo_global, games_played, last_updated
        """
        result = self.conn.execute(
            """
            SELECT * FROM elo_ratings
            WHERE games_played >= ?
            ORDER BY elo_global DESC
            LIMIT ?
        """,
            [min_games, n],
        ).arrow()

        return ibis.memtable(self._arrow_to_pydict(result))

    def get_all_ratings(self) -> Table:
        """
        Get all ratings as Ibis Table.

        Returns:
            Ibis Table with all elo_ratings data
        """
        result = self.conn.execute("SELECT * FROM elo_ratings ORDER BY elo_global DESC").arrow()
        return ibis.memtable(self._arrow_to_pydict(result))

    def get_all_history(self) -> Table:
        """
        Get all comparison history as Ibis Table.

        Returns:
            Ibis Table with all elo_history data
        """
        result = self.conn.execute("SELECT * FROM elo_history ORDER BY timestamp").arrow()
        return ibis.memtable(self._arrow_to_pydict(result))

    def _arrow_to_pydict(self, arrow_object: Any) -> Dict[str, Any]:
        """Convert DuckDB Arrow results into a dictionary for Ibis memtable usage."""

        if isinstance(arrow_object, pa.RecordBatchReader):
            table: pa.Table | None = arrow_object.read_all()
        elif isinstance(arrow_object, pa.Table):
            table = arrow_object
        else:
            table = None
            for attr in ("read_all", "to_table", "to_arrow_table"):
                method = getattr(arrow_object, attr, None)
                if not callable(method):
                    continue

                result = method()
                if isinstance(result, pa.RecordBatchReader):
                    table = result.read_all()
                    break
                if isinstance(result, pa.Table):
                    table = result
                    break

            if table is None:
                to_pydict = getattr(arrow_object, "to_pydict", None)
                if callable(to_pydict):
                    data = to_pydict()
                    if isinstance(data, dict):
                        return data

                raise TypeError(f"Unsupported Arrow object type: {type(arrow_object)!r}")

        if not isinstance(table, pa.Table):
            raise TypeError(f"Expected pyarrow.Table after conversion, got {type(table)!r}")

        return table.to_pydict()

    def export_to_parquet(self) -> None:
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

    def stats(self) -> Dict[str, Any]:
        """
        Get ranking store statistics.

        Returns:
            dict with stats about ratings and history
        """
        ratings_count_result = self.conn.execute("SELECT COUNT(*) FROM elo_ratings").fetchone()
        ratings_count = ratings_count_result[0] if ratings_count_result is not None else 0

        comparisons_count_result = self.conn.execute("SELECT COUNT(*) FROM elo_history").fetchone()
        comparisons_count = comparisons_count_result[0] if comparisons_count_result is not None else 0

        avg_games_result = self.conn.execute(
            """
            SELECT AVG(games_played) FROM elo_ratings
        """).fetchone()
        avg_games = (avg_games_result[0] if avg_games_result is not None else 0) or 0

        top_elo_result = self.conn.execute(
            """
            SELECT MAX(elo_global) FROM elo_ratings
        """).fetchone()
        top_elo = (top_elo_result[0] if top_elo_result is not None else 1500) or 1500

        bottom_elo_result = self.conn.execute(
            """
            SELECT MIN(elo_global) FROM elo_ratings
        """).fetchone()
        bottom_elo = (bottom_elo_result[0] if bottom_elo_result is not None else 1500) or 1500

        return {
            "total_posts": ratings_count,
            "total_comparisons": comparisons_count,
            "avg_games_per_post": avg_games,
            "highest_elo": top_elo,
            "lowest_elo": bottom_elo,
        }
