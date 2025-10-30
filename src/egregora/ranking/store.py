"""DuckDB-backed ranking store for efficient updates and queries."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import ibis
from ibis.expr.types import Table

from egregora.sql_templates import render_sql_template

logger = logging.getLogger(__name__)


ELO_PROFILES_TABLE = "elo_profiles"
ELO_PROFILE_STATS_TABLE = "elo_profile_stats"
ELO_RATINGS_TABLE = "elo_ratings"
ELO_HISTORY_TABLE = "elo_history"
ELO_PROFILE_STATS_LAST_SEEN_INDEX = "idx_profile_stats_last_seen"
ELO_PROFILE_STATS_COMPARISONS_INDEX = "idx_profile_stats_comparisons"
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
        self.ibis_conn = ibis.duckdb.from_connection(self.conn)

        logger.info(f"Ranking store initialized: {self.db_path}")

    def _init_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        # Judge profiles table (identity)
        self.conn.execute(
            render_sql_template(
                "ranking_elo_profiles_table.sql.jinja",
                table_name=ELO_PROFILES_TABLE,
            )
        )

        # Judge profile stats table
        self.conn.execute(
            render_sql_template(
                "ranking_elo_profile_stats_table.sql.jinja",
                table_name=ELO_PROFILE_STATS_TABLE,
                profiles_table_name=ELO_PROFILES_TABLE,
            )
        )

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
                profiles_table_name=ELO_PROFILES_TABLE,
            )
        )

        # Create indexes for efficient queries
        self.conn.execute(
            render_sql_template(
                "create_index.sql.jinja",
                index_name=ELO_PROFILE_STATS_LAST_SEEN_INDEX,
                table_name=ELO_PROFILE_STATS_TABLE,
                columns=["last_seen"],
            )
        )
        self.conn.execute(
            render_sql_template(
                "create_index.sql.jinja",
                index_name=ELO_PROFILE_STATS_COMPARISONS_INDEX,
                table_name=ELO_PROFILE_STATS_TABLE,
                columns=["comparisons"],
            )
        )
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

    @staticmethod
    def _to_utc_naive(ts: datetime) -> datetime:
        """Convert timezone-aware timestamps to naive UTC for DuckDB."""

        if ts.tzinfo is None:
            return ts
        return ts.astimezone(UTC).replace(tzinfo=None)

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

        ratings = self.ibis_conn.table(ELO_RATINGS_TABLE)
        existing_rows = (
            ratings.filter(ratings.post_id.isin(post_ids)).select(ratings.post_id)
        ).to_pyarrow()
        existing_ids = (
            set(existing_rows.column("post_id").to_pylist())
            if existing_rows.num_rows
            else set()
        )

        new_post_ids = [post_id for post_id in post_ids if post_id not in existing_ids]
        if not new_post_ids:
            return 0

        now = self._to_utc_naive(datetime.now(UTC))
        ratings_schema = ratings.schema()
        payload_schema = ibis.schema(
            {
                "post_id": ratings_schema["post_id"],
                "elo_global": ratings_schema["elo_global"],
                "games_played": ratings_schema["games_played"],
                "last_updated": ratings_schema["last_updated"],
            }
        )
        payload_expr = ibis.memtable(
            [
                {
                    "post_id": post_id,
                    "elo_global": 1500.0,
                    "games_played": 0,
                    "last_updated": now,
                }
                for post_id in new_post_ids
            ],
            schema=payload_schema,
        )

        self.ibis_conn.insert(ELO_RATINGS_TABLE, payload_expr)
        logger.info(f"Initialized {len(new_post_ids)} new posts with default ELO 1500")

        return len(new_post_ids)

    def get_rating(self, post_id: str) -> dict[str, Any] | None:
        """
        Get rating for a specific post.

        Args:
            post_id: Post ID

        Returns:
            dict with elo_global and games_played, or None if not found
        """
        ratings = self.ibis_conn.table(ELO_RATINGS_TABLE)
        result = (
            ratings.filter(ratings.post_id == post_id)
            .select(ratings.elo_global, ratings.games_played)
            .to_pyarrow()
        )

        if result.num_rows == 0:
            return None

        elo = float(result.column("elo_global").to_pylist()[0])
        games = int(result.column("games_played").to_pylist()[0])
        return {"elo_global": elo, "games_played": games}

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
        ratings = self.ibis_conn.table(ELO_RATINGS_TABLE)
        if ratings.count().execute() == 0:
            raise ValueError("Cannot update ratings for an empty rankings table")

        now = self._to_utc_naive(datetime.now(UTC))

        post_id_type = ratings.schema()["post_id"]
        elo_type = ratings.schema()["elo_global"]
        games_type = ratings.schema()["games_played"]
        timestamp_type = ratings.schema()["last_updated"]

        post_a_literal = ibis.literal(post_a, type=post_id_type)
        post_b_literal = ibis.literal(post_b, type=post_id_type)

        exists_a = ratings.filter(ratings.post_id == post_a_literal).count().execute()
        if exists_a == 0:
            raise KeyError(f"Rating row for post '{post_a}' is missing")

        exists_b = ratings.filter(ratings.post_id == post_b_literal).count().execute()
        if exists_b == 0:
            raise KeyError(f"Rating row for post '{post_b}' is missing")

        elo_literal_a = ibis.literal(new_elo_a, type=elo_type)
        elo_literal_b = ibis.literal(new_elo_b, type=elo_type)
        now_literal = ibis.literal(now, type=timestamp_type)

        target_filter = (ratings.post_id == post_a_literal) | (ratings.post_id == post_b_literal)

        updated = ratings.mutate(
            elo_global=ibis.case()
            .when(ratings.post_id == post_a_literal, elo_literal_a)
            .when(ratings.post_id == post_b_literal, elo_literal_b)
            .else_(ratings.elo_global)
            .end(),
            games_played=ibis.case()
            .when(target_filter, ratings.games_played + ibis.literal(1, type=games_type))
            .else_(ratings.games_played)
            .end(),
            last_updated=ibis.ifelse(target_filter, now_literal, ratings.last_updated),
        )

        self.ibis_conn.insert(ELO_RATINGS_TABLE, updated, overwrite=True)

        logger.debug(f"Updated ratings: {post_a}={new_elo_a:.0f}, {post_b}={new_elo_b:.0f}")

        return new_elo_a, new_elo_b

    def save_comparison(self, comparison_data: dict[str, Any]) -> None:
        """
        Save comparison to history.

        Args:
            comparison_data: dict with keys:
                - comparison_id: str
                - timestamp: datetime
                - profile_id: str
                - profile_alias: str | None (optional)
                - profile_bio: str | None (optional)
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

        self._upsert_profile(
            profile_id=comparison_data["profile_id"],
            alias=comparison_data.get("profile_alias"),
            bio=comparison_data.get("profile_bio"),
        )

        history = self.ibis_conn.table(ELO_HISTORY_TABLE)
        history_schema = history.schema()
        record = {
            "comparison_id": comparison_data["comparison_id"],
            "timestamp": self._to_utc_naive(comparison_data["timestamp"]),
            "profile_id": comparison_data["profile_id"],
            "post_a": comparison_data["post_a"],
            "post_b": comparison_data["post_b"],
            "winner": comparison_data["winner"],
            "comment_a": comparison_data["comment_a"],
            "stars_a": comparison_data["stars_a"],
            "comment_b": comparison_data["comment_b"],
            "stars_b": comparison_data["stars_b"],
        }

        payload_schema = ibis.schema({name: history_schema[name] for name in record.keys()})
        payload_expr = ibis.memtable([record], schema=payload_schema)

        self.ibis_conn.insert(ELO_HISTORY_TABLE, payload_expr)

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
            ratings = self.ibis_conn.table(ELO_RATINGS_TABLE)
            candidates = (
                ratings.order_by([ratings.games_played, ibis.random()])
                .limit(n)
                .select(ratings.post_id)
                .to_pyarrow()
            )
            return candidates.column("post_id").to_pylist()
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
        history = self.ibis_conn.table(ELO_HISTORY_TABLE)
        post_ref = ibis.literal(post_id)

        return (
            history.filter((history.post_a == post_ref) | (history.post_b == post_ref))
            .select(
                history.profile_id,
                history.timestamp,
                comment=ibis.ifelse(history.post_a == post_ref, history.comment_a, history.comment_b),
                stars=ibis.ifelse(history.post_a == post_ref, history.stars_a, history.stars_b),
            )
            .order_by(history.timestamp)
        )

    def get_top_posts(self, n: int = 10, min_games: int = 5) -> Table:
        """
        Get top-rated posts.

        Args:
            n: Number of posts to return
            min_games: Minimum number of games for confidence

        Returns:
            Ibis Table with post_id, elo_global, games_played, last_updated
        """
        ratings = self.ibis_conn.table(ELO_RATINGS_TABLE)
        return (
            ratings.filter(ratings.games_played >= min_games)
            .order_by(ratings.elo_global.desc())
            .limit(n)
        )

    def get_all_ratings(self) -> Table:
        """
        Get all ratings as Ibis Table.

        Returns:
            Ibis Table with all elo_ratings data
        """
        ratings = self.ibis_conn.table(ELO_RATINGS_TABLE)
        return ratings.order_by(ratings.elo_global.desc())

    def get_all_history(self) -> Table:
        """
        Get all comparison history as Ibis Table.

        Returns:
            Ibis Table with all elo_history data
        """
        history = self.ibis_conn.table(ELO_HISTORY_TABLE)
        return history.order_by(history.timestamp)

    def get_all_profiles(self) -> Table:
        """Return judge profile statistics as an Ibis table.

        Columns: profile_id, alias, bio, comparisons, first_seen, last_seen.
        """

        profiles = self.ibis_conn.table(ELO_PROFILES_TABLE)
        stats = self.ibis_conn.table(ELO_PROFILE_STATS_TABLE)
        return (
            profiles.join(stats, profiles.profile_id == stats.profile_id)
            .select(
                profiles.profile_id,
                stats["alias"],
                stats["bio"],
                stats["comparisons"],
                profiles.first_seen,
                stats["last_seen"],
            )
            .order_by(stats["last_seen"].desc())
        )

    def export_to_parquet(self) -> None:
        """
        Export DuckDB tables to Parquet for sharing/analytics.

        Creates:
            - rankings/elo_profiles.parquet
            - rankings/elo_profile_stats.parquet
            - rankings/elo_ratings.parquet
            - rankings/elo_history.parquet
        """
        profiles_path = self.rankings_dir / "elo_profiles.parquet"
        profile_stats_path = self.rankings_dir / "elo_profile_stats.parquet"
        ratings_path = self.rankings_dir / "elo_ratings.parquet"
        history_path = self.rankings_dir / "elo_history.parquet"

        self.ibis_conn.to_parquet(self.ibis_conn.table(ELO_PROFILES_TABLE), profiles_path)
        self.ibis_conn.to_parquet(
            self.ibis_conn.table(ELO_PROFILE_STATS_TABLE), profile_stats_path
        )
        self.ibis_conn.to_parquet(self.ibis_conn.table(ELO_RATINGS_TABLE), ratings_path)
        self.ibis_conn.to_parquet(self.ibis_conn.table(ELO_HISTORY_TABLE), history_path)

        logger.info(f"Exported rankings to Parquet: {self.rankings_dir}")

    def stats(self) -> dict[str, Any]:
        """
        Get ranking store statistics.

        Returns:
            dict with stats about ratings and history
        """
        profiles = self.ibis_conn.table(ELO_PROFILES_TABLE)
        ratings = self.ibis_conn.table(ELO_RATINGS_TABLE)
        history = self.ibis_conn.table(ELO_HISTORY_TABLE)

        profiles_count = int(profiles.count().execute() or 0)
        ratings_count = int(ratings.count().execute() or 0)
        comparisons_count = int(history.count().execute() or 0)

        avg_games_value = ratings.games_played.mean().execute()
        top_elo_value = ratings.elo_global.max().execute()
        bottom_elo_value = ratings.elo_global.min().execute()

        avg_games = float(avg_games_value) if avg_games_value is not None else 0.0
        top_elo = float(top_elo_value) if top_elo_value is not None else 1500.0
        bottom_elo = float(bottom_elo_value) if bottom_elo_value is not None else 1500.0

        return {
            "total_profiles": profiles_count,
            "total_posts": ratings_count,
            "total_comparisons": comparisons_count,
            "avg_games_per_post": avg_games,
            "highest_elo": top_elo,
            "lowest_elo": bottom_elo,
        }

    def _upsert_profile(self, *, profile_id: str, alias: str | None, bio: str | None) -> None:
        """Ensure judge metadata exists and update activity counters."""

        normalized_alias = alias.strip() if isinstance(alias, str) else None
        if normalized_alias == "":
            normalized_alias = None

        normalized_bio = bio.strip() if isinstance(bio, str) else None
        if normalized_bio == "":
            normalized_bio = None

        now = self._to_utc_naive(datetime.now(UTC))

        profiles = self.ibis_conn.table(ELO_PROFILES_TABLE)
        profile_schema = profiles.schema()
        profile_exists = (
            profiles.filter(profiles.profile_id == profile_id).count().execute() > 0
        )
        if not profile_exists:
            profile_payload = ibis.memtable(
                [
                    {
                        "profile_id": profile_id,
                        "first_seen": now,
                    }
                ],
                schema=ibis.schema(
                    {
                        "profile_id": profile_schema["profile_id"],
                        "first_seen": profile_schema["first_seen"],
                    }
                ),
            )
            self.ibis_conn.insert(ELO_PROFILES_TABLE, profile_payload)

        stats = self.ibis_conn.table(ELO_PROFILE_STATS_TABLE)
        stats_schema = stats.schema()
        profile_key_literal = ibis.literal(profile_id, type=stats_schema["profile_id"])
        existing_count = (
            stats.filter(stats.profile_id == profile_key_literal).count().execute()
        )

        if existing_count == 0:
            new_row = {
                "profile_id": profile_id,
                "alias": normalized_alias,
                "bio": normalized_bio,
                "comparisons": 1,
                "last_seen": now,
            }
            new_schema = ibis.schema(
                {
                    "profile_id": stats_schema["profile_id"],
                    "alias": stats_schema["alias"],
                    "bio": stats_schema["bio"],
                    "comparisons": stats_schema["comparisons"],
                    "last_seen": stats_schema["last_seen"],
                }
            )
            payload = ibis.memtable([new_row], schema=new_schema)
            self.ibis_conn.insert(ELO_PROFILE_STATS_TABLE, payload)
            return

        current_arrow = (
            stats.filter(stats.profile_id == profile_key_literal)
            .select(
                stats["alias"].name("alias"),
                stats["bio"].name("bio"),
                stats["comparisons"].name("comparisons"),
            )
            .to_pyarrow()
        )

        if current_arrow.num_rows == 0:
            raise RuntimeError("Expected an existing stats row but none was found")

        current_alias = current_arrow.column("alias").to_pylist()[0]
        current_bio = current_arrow.column("bio").to_pylist()[0]
        current_comparisons = current_arrow.column("comparisons").to_pylist()[0]

        next_alias = normalized_alias if normalized_alias is not None else current_alias
        next_bio = normalized_bio if normalized_bio is not None else current_bio
        next_comparisons = int(current_comparisons) + 1

        column_schema = ibis.schema(
            {
                "profile_id": stats_schema["profile_id"],
                "alias": stats_schema["alias"],
                "bio": stats_schema["bio"],
                "comparisons": stats_schema["comparisons"],
                "last_seen": stats_schema["last_seen"],
            }
        )

        updated_row = {
            "profile_id": profile_id,
            "alias": next_alias,
            "bio": next_bio,
            "comparisons": next_comparisons,
            "last_seen": now,
        }

        updated_mem = ibis.memtable([updated_row], schema=column_schema)
        remaining_expr = stats.filter(stats.profile_id != profile_key_literal).select(
            *[stats[name] for name in column_schema.names]
        )
        combined_expr = remaining_expr.union(updated_mem, distinct=False)

        self.ibis_conn.insert(ELO_PROFILE_STATS_TABLE, combined_expr, overwrite=True)
