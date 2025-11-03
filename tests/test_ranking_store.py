from __future__ import annotations

from egregora.knowledge.ranking.store import RankingStore


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
    assert inserted_first == 2

    inserted_second = store.initialize_ratings(["post_a", "post_b", "post_c"])
    assert inserted_second == 1

    rows = _fetch_ratings(store, ["post_a", "post_b", "post_c"])
    assert [row[0] for row in rows] == ["post_a", "post_b", "post_c"]


def test_update_ratings_updates_both_posts_atomically(tmp_path) -> None:
    store = RankingStore(tmp_path)
    store.initialize_ratings(["post_a", "post_b", "post_c"])

    before_rows = _fetch_ratings(store, ["post_a", "post_b"])
    before_last_updated = [row[3] for row in before_rows]

    new_elo_a, new_elo_b = 1600.0, 1400.0
    result = store.update_ratings("post_a", "post_b", new_elo_a, new_elo_b)
    assert result == (new_elo_a, new_elo_b)

    after_rows = _fetch_ratings(store, ["post_a", "post_b", "post_c"])
    post_a, post_b, post_c = after_rows

    assert post_a[1] == new_elo_a
    assert post_b[1] == new_elo_b
    assert post_a[2] == 1
    assert post_b[2] == 1
    assert post_c[2] == 0

    assert post_a[3] == post_b[3]
    assert post_a[3] != before_last_updated[0]

