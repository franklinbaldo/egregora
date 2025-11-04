from __future__ import annotations

from egregora.knowledge.ranking.store import RankingStore

EXPECTED_INSERTED_FIRST = 2
EXPECTED_INSERTED_SECOND = 1
NEW_ELO_A = 1600.0
NEW_ELO_B = 1400.0
GAMES_PLAYED_A = 1
GAMES_PLAYED_B = 1
GAMES_PLAYED_C = 0


def _fetch_ratings(store: RankingStore, post_ids: list[str]) -> list[tuple]:
    placeholders = ",".join(["?"] * len(post_ids))
    query = f"""
        SELECT post_id, elo_global, games_played, last_updated
        FROM elo_ratings
        WHERE post_id IN ({placeholders})
        ORDER BY post_id
    """
    return store.conn.execute(query, post_ids).fetchall()


def test_initialize_ratings_idempotent_batch_insert(tmp_path) -> None:
    store = RankingStore(tmp_path)

    inserted_first = store.initialize_ratings(["post_a", "post_b", "post_a"])
    assert inserted_first == EXPECTED_INSERTED_FIRST

    inserted_second = store.initialize_ratings(["post_a", "post_b", "post_c"])
    assert inserted_second == EXPECTED_INSERTED_SECOND

    rows = _fetch_ratings(store, ["post_a", "post_b", "post_c"])
    assert [row[0] for row in rows] == ["post_a", "post_b", "post_c"]


def test_update_ratings_updates_both_posts_atomically(tmp_path) -> None:
    store = RankingStore(tmp_path)
    store.initialize_ratings(["post_a", "post_b", "post_c"])

    before_rows = _fetch_ratings(store, ["post_a", "post_b"])
    before_last_updated = [row[3] for row in before_rows]

    result = store.update_ratings("post_a", "post_b", NEW_ELO_A, NEW_ELO_B)
    assert result == (NEW_ELO_A, NEW_ELO_B)

    after_rows = _fetch_ratings(store, ["post_a", "post_b", "post_c"])
    post_a, post_b, post_c = after_rows

    assert post_a[1] == NEW_ELO_A
    assert post_b[1] == NEW_ELO_B
    assert post_a[2] == GAMES_PLAYED_A
    assert post_b[2] == GAMES_PLAYED_B
    assert post_c[2] == GAMES_PLAYED_C

    assert post_a[3] == post_b[3]
    assert post_a[3] != before_last_updated[0]
