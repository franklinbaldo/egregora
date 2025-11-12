from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import ibis
from egregora.agents.ranking.store import RankingStore

from egregora.agents.shared.annotations import ANNOTATION_AUTHOR, AnnotationStore
from egregora.config.schema import create_default_config
from egregora.database import schemas as database_schema
from egregora.enrichment.core import EnrichmentRuntimeContext, enrich_table
from egregora.utils.batch import BatchPromptResult
from egregora.utils.cache import EnrichmentCache
from tests.helpers.storage import InMemoryEnrichmentStorage

if TYPE_CHECKING:
    import duckdb


class DummyBatchClient:
    """Minimal Gemini batch client stub for enrichment tests."""

    def __init__(self, model: str):
        self.default_model = model

    def generate_content(self, requests, **_: object):
        results: list[BatchPromptResult] = [
            BatchPromptResult(
                tag=getattr(request, "tag", None),
                response=SimpleNamespace(text=f"Generated content for {getattr(request, 'tag', 'unknown')}"),
                error=None,
            )
            for request in requests
        ]
        return results

    def upload_file(self, *, path: str, display_name: str | None = None):  # pragma: no cover - unused
        return SimpleNamespace(uri=f"stub://{Path(path).name}", mime_type="image/jpeg")


def _create_conversation_table(tmp_path: Path) -> tuple[duckdb.DuckDBPyConnection, str]:
    db_path = tmp_path / "conversation.duckdb"
    backend = ibis.duckdb.connect(str(db_path))
    table_name = "conversation_log"
    # Pass raw DuckDB connection (not Ibis backend)
    database_schema.create_table_if_not_exists(
        backend.con,
        table_name,
        database_schema.CONVERSATION_SCHEMA,
    )
    return backend.con, table_name


def test_ranking_store_bulk_initialize_and_update(tmp_path: Path):
    store = RankingStore(tmp_path / "rankings")

    initial_posts = ["post-a", "post-b"]
    inserted = store.initialize_ratings(initial_posts)
    assert inserted == len(set(initial_posts))

    next_posts = ["post-a", "post-c"]
    inserted_again = store.initialize_ratings(next_posts)
    assert inserted_again == len({"post-c"})

    store.update_ratings("post-a", "post-b", 1600.0, 1400.0)

    rating_a = store.get_rating("post-a")
    rating_b = store.get_rating("post-b")

    assert rating_a == {"elo_global": 1600.0, "games_played": 1}
    assert rating_b == {"elo_global": 1400.0, "games_played": 1}


def test_ranking_store_initialize_handles_empty_batches(tmp_path: Path):
    store = RankingStore(tmp_path / "rankings")

    assert store.initialize_ratings([]) == 0

    temp_tables = store.conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE lower(table_name) = lower('__elo_init_posts')
        """
    ).fetchall()

    assert temp_tables == []


def test_annotation_store_uses_identity_column(tmp_path: Path):
    store = AnnotationStore(tmp_path / "annotations.duckdb")

    first = store.save_annotation("msg-1", "message", "First comment")
    second = store.save_annotation("msg-1", "message", "Second comment")

    assert second.id == first.id + 1

    rows = store._connection.execute(
        """
        SELECT id, parent_id, parent_type, author, commentary
        FROM annotations
        ORDER BY id
        """
    ).fetchall()

    assert rows == [
        (first.id, "msg-1", "message", ANNOTATION_AUTHOR, "First comment"),
        (second.id, "msg-1", "message", ANNOTATION_AUTHOR, "Second comment"),
    ]


def test_enrich_table_persists_results(tmp_path: Path):
    now = datetime.now(UTC)
    base_row = {
        "timestamp": now,
        "date": now.date(),
        "author": "user-123",
        "message": "Check this link https://example.com/article",
        "original_line": "",
        "tagged_line": "",
        "message_id": "1",
    }

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir(parents=True)
    posts_dir.mkdir(parents=True)

    DummyBatchClient("text-model")
    DummyBatchClient("vision-model")
    cache = EnrichmentCache(tmp_path / "cache")

    conn, table_name = _create_conversation_table(tmp_path)
    backend = ibis.duckdb.from_connection(conn)

    # Create memtable using ibis.memtable (not backend.memtable)
    messages_table = ibis.memtable([base_row], schema=database_schema.CONVERSATION_SCHEMA)

    # MODERN (Phase 2): Create config and context
    config = create_default_config(tmp_path)
    config = config.model_copy(
        deep=True,
        update={
            "enrichment": config.enrichment.model_copy(update={"enable_media": False}),
        },
    )

    # Create mock output_format with enrichments storage
    output_format = SimpleNamespace(enrichments=InMemoryEnrichmentStorage())

    enrichment_context = EnrichmentRuntimeContext(
        cache=cache,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
        output_format=output_format,
        duckdb_connection=backend,  # Pass Ibis backend, not raw connection
        target_table=table_name,
    )

    try:
        combined = enrich_table(
            messages_table,
            media_mapping={},
            config=config,
            context=enrichment_context,
        )
    finally:
        cache.close()

    assert combined.count().execute() >= messages_table.count().execute()

    persisted_rows = conn.execute(f"SELECT author, message FROM {table_name} ORDER BY timestamp").fetchall()

    assert any(row[0] == ANNOTATION_AUTHOR for row in persisted_rows)
