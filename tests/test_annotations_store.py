from __future__ import annotations

from pathlib import Path

import duckdb

from egregora.knowledge.annotations import AnnotationStore


def test_annotations_store_migrates_legacy_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "annotations.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE annotations (
            id INTEGER,
            msg_id VARCHAR,
            parent_annotation_id INTEGER,
            author VARCHAR,
            commentary VARCHAR,
            created_at TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        INSERT INTO annotations (id, msg_id, parent_annotation_id, author, commentary, created_at)
        VALUES
            (1, 'msg-1', NULL, 'author', 'First annotation', '2024-01-01T00:00:00Z'),
            (2, NULL, 1, 'author', 'Reply annotation', '2024-01-01T01:00:00Z')
        """
    )
    conn.close()

    store = AnnotationStore(db_path)

    columns = {
        row[1]
        for row in store._connection.execute("PRAGMA table_info('annotations')").fetchall()
    }
    assert "parent_id" in columns
    assert "parent_type" in columns
    assert "msg_id" not in columns
    assert "parent_annotation_id" not in columns

    annotations_for_message = store.list_annotations_for_message("msg-1")
    assert len(annotations_for_message) == 1
    assert annotations_for_message[0].parent_type == "message"
    assert annotations_for_message[0].parent_id == "msg-1"

    all_annotations = {annotation.id: annotation for annotation in store.iter_all_annotations()}
    assert all_annotations[2].parent_type == "annotation"
    assert all_annotations[2].parent_id == "1"
