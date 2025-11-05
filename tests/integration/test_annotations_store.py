from __future__ import annotations

import concurrent.futures

from egregora.database.annotations import AnnotationStore

NUM_CONCURRENT_INSERTS = 10


def test_annotation_store_generates_incremental_ids(tmp_path):
    db_path = tmp_path / "annotations.duckdb"
    store = AnnotationStore(db_path)

    first = store.save_annotation("message-1", "message", "First comment")
    second = store.save_annotation("message-2", "message", "Second comment")

    assert first.id >= 1
    assert second.id == first.id + 1


def test_concurrent_annotation_inserts_produce_unique_sequential_ids(tmp_path):
    db_path = tmp_path / "annotations.duckdb"
    # Initialize table before concurrent writes
    AnnotationStore(db_path)

    def insert_annotation(idx: int) -> int:
        store = AnnotationStore(db_path)
        annotation = store.save_annotation(
            f"message-{idx}", "message", f"Concurrent annotation {idx}"
        )
        return annotation.id

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(insert_annotation, idx) for idx in range(1, NUM_CONCURRENT_INSERTS + 1)
        ]
        ids = [future.result() for future in futures]

    assert len(ids) == NUM_CONCURRENT_INSERTS
    assert len(set(ids)) == len(ids)
    assert sorted(ids) == list(range(1, len(ids) + 1))


def test_annotation_store_identity_survives_restart(tmp_path):
    db_path = tmp_path / "annotations.duckdb"
    store = AnnotationStore(db_path)

    first = store.save_annotation("message-1", "message", "First comment")
    second = store.save_annotation("message-2", "message", "Second comment")

    store = AnnotationStore(db_path)
    third = store.save_annotation("message-3", "message", "Third comment")

    assert second.id == first.id + 1
    assert third.id == second.id + 1
