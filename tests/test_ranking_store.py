from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from egregora.ranking.store import RankingStore


@pytest.fixture()
def ranking_store(tmp_path: Path) -> RankingStore:
    store = RankingStore(tmp_path)
    yield store
    store.conn.close()


def _comparison_payload(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "comparison_id": "cmp-1",
        "timestamp": now,
        "profile_id": "judge-123",
        "profile_alias": "Curious Critic",
        "profile_bio": "Keeps score on long-form pieces.",
        "post_a": "post-a",
        "post_b": "post-b",
        "winner": "A",
        "comment_a": "Great structure.",
        "stars_a": 5,
        "comment_b": "Needs more references.",
        "stars_b": 3,
    }
    payload.update(overrides)
    return payload


def test_profile_metadata_upsert_and_history_insert(ranking_store: RankingStore) -> None:
    ranking_store.initialize_ratings(["post-a", "post-b"])

    ranking_store.save_comparison(_comparison_payload())

    profile_row = ranking_store.conn.execute(
        """
        SELECT
            p.profile_id,
            s.alias,
            s.bio,
            s.comparisons,
            p.first_seen,
            s.last_seen
        FROM elo_profiles AS p
        JOIN elo_profile_stats AS s ON p.profile_id = s.profile_id
        """
    ).fetchone()

    assert profile_row is not None
    assert profile_row[0] == "judge-123"
    assert profile_row[1] == "Curious Critic"
    assert profile_row[2] == "Keeps score on long-form pieces."
    assert profile_row[3] == 1

    first_seen = profile_row[4]
    last_seen = profile_row[5]
    assert first_seen == last_seen

    ranking_store.save_comparison(
        _comparison_payload(
            comparison_id="cmp-2",
            profile_alias="Critical Curator",
            stars_a=4,
            stars_b=2,
            winner="B",
        )
    )

    updated_profile = ranking_store.conn.execute(
        """
        SELECT s.alias, s.comparisons, p.first_seen, s.last_seen
        FROM elo_profiles AS p
        JOIN elo_profile_stats AS s ON p.profile_id = s.profile_id
        WHERE p.profile_id = ?
        """,
        ["judge-123"],
    ).fetchone()

    assert updated_profile is not None
    assert updated_profile[0] == "Critical Curator"
    assert updated_profile[1] == 2
    assert updated_profile[2] == first_seen  # first_seen is stable
    assert updated_profile[3] != first_seen  # last_seen updated

    history_rows = ranking_store.conn.execute(
        "SELECT COUNT(*) FROM elo_history WHERE profile_id = ?",
        ["judge-123"],
    ).fetchone()
    assert history_rows == (2,)


def test_history_enforces_profile_foreign_key(ranking_store: RankingStore) -> None:
    ranking_store.initialize_ratings(["post-a", "post-b"])

    with pytest.raises(duckdb.ConstraintException):
        ranking_store.conn.execute(
            """
            INSERT INTO elo_history (
                comparison_id,
                timestamp,
                profile_id,
                post_a,
                post_b,
                winner,
                comment_a,
                stars_a,
                comment_b,
                stars_b
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "cmp-missing-profile",
                datetime.now(UTC),
                "does-not-exist",
                "post-a",
                "post-b",
                "A",
                "missing profile",
                5,
                "still missing",
                4,
            ],
        )
