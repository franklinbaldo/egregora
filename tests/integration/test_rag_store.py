"""Regression tests for the RAG vector store."""

from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb
import ibis
import pytest

ROW_COUNT = 42
THRESHOLD = 10
NLIST = 8
EMBEDDING_DIM = 1536


def _vector_store_row(store_module, **overrides):
    """Construct a row matching VECTOR_STORE_SCHEMA with sensible defaults."""

    base = dict.fromkeys(store_module.VECTOR_STORE_SCHEMA.names)

    defaults = {
        "chunk_id": overrides.get("chunk_id"),
        "document_type": "post",
        "document_id": overrides.get("chunk_id"),
        "chunk_index": 0,
        "content": overrides.get("chunk_id"),
        "embedding": overrides.get("embedding", []),
        "tags": overrides.get("tags", []),
        "authors": overrides.get("authors", []),
    }
    defaults.update(overrides)

    if defaults.get("chunk_id") is None:
        raise ValueError("chunk_id is required for vector store rows")

    if defaults.get("document_id") is None:
        defaults["document_id"] = defaults["chunk_id"]

    if defaults.get("content") is None:
        defaults["content"] = defaults["chunk_id"]

    base.update(defaults)
    return base


def test_rag_metadata_schema_includes_nullable_checksum():
    store_module = _load_vector_store()
    schema = store_module.database_schema.RAG_CHUNKS_METADATA_SCHEMA

    assert list(schema.names) == ["path", "mtime_ns", "size", "row_count", "checksum"]
    assert schema["row_count"].is_integer()
    checksum_dtype = schema["checksum"]
    assert checksum_dtype.is_string()
    assert checksum_dtype.nullable


def test_vector_store_does_not_override_existing_backend(tmp_path, monkeypatch):
    """Instantiating a store must not clobber an existing Ibis backend."""

    previous_backend = ibis.get_backend()
    custom_backend = ibis.duckdb.connect()
    ibis.set_backend(custom_backend)

    try:
        store_module = _load_vector_store()
        monkeypatch.setattr(store_module.VectorStore, "_init_vss", lambda self: None)
        store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=duckdb.connect(":memory:"))
        try:
            assert ibis.get_backend() is custom_backend
        finally:
            store.close()
    finally:
        ibis.set_backend(previous_backend)


def test_add_accepts_memtable_from_default_backend(tmp_path, monkeypatch):
    """VectorStore.add must materialize tables built on other backends."""

    store_module = _load_vector_store()
    monkeypatch.setattr(store_module.VectorStore, "_init_vss", lambda self: None)
    monkeypatch.setattr(store_module.VectorStore, "_rebuild_index", lambda self: None)

    other_backend = ibis.duckdb.connect()
    previous_backend = ibis.get_backend()
    ibis.set_backend(other_backend)

    try:
        store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=duckdb.connect(":memory:"))
        try:
            first_batch = ibis.memtable(
                [
                    _vector_store_row(
                        store_module,
                        chunk_id="chunk-1",
                        document_id="doc-1",
                        chunk_index=0,
                        content="hello",
                        embedding=[0.0, 1.0],
                        tags=["tag"],
                    )
                ],
                schema=store_module.VECTOR_STORE_SCHEMA,
            )
            store.add(first_batch)

            second_batch = ibis.memtable(
                [
                    _vector_store_row(
                        store_module,
                        chunk_id="chunk-2",
                        document_id="doc-2",
                        chunk_index=0,
                        content="world",
                        embedding=[1.0, 0.0],
                        tags=["tag"],
                    )
                ],
                schema=store_module.VECTOR_STORE_SCHEMA,
            )
            store.add(second_batch)

            stored_rows = store.get_all().order_by("chunk_id").execute()
            assert list(stored_rows["chunk_id"]) == ["chunk-1", "chunk-2"]
        finally:
            store.close()
    finally:
        ibis.set_backend(previous_backend)


def test_add_rejects_tables_with_incorrect_schema(tmp_path, monkeypatch):
    """Adding rows must fail fast when the input schema diverges."""

    store_module = _load_vector_store()
    monkeypatch.setattr(store_module.VectorStore, "_init_vss", lambda self: None)
    monkeypatch.setattr(store_module.VectorStore, "_rebuild_index", lambda self: None)

    store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=duckdb.connect(":memory:"))

    try:
        missing_column_rows = [
            {
                "chunk_id": "chunk-1",
                "content": "hello",
                "embedding": [0.0, 1.0],
            }
        ]

        with pytest.raises(ValueError, match="missing columns"):
            store.add(ibis.memtable(missing_column_rows))

        valid_rows = [
            _vector_store_row(
                store_module,
                chunk_id="chunk-1",
                document_id="doc-1",
                chunk_index=0,
                content="hello",
                embedding=[0.0, 1.0],
                tags=["tag"],
            )
        ]
        store.add(ibis.memtable(valid_rows, schema=store_module.VECTOR_STORE_SCHEMA))

        extra_column_row = _vector_store_row(
            store_module,
            chunk_id="chunk-2",
            document_id="doc-2",
            chunk_index=0,
            content="world",
            embedding=[1.0, 0.0],
            tags=["tag"],
        )
        extra_column_row["extra"] = "value"

        with pytest.raises(ValueError, match="unexpected columns"):
            store.add(ibis.memtable([extra_column_row]))
    finally:
        store.close()


def _load_vector_store():
    """Load the vector store module."""
    from egregora.agents.tools.rag import store

    return store


def _table_columns(connection, table_name: str) -> list[tuple[str, bool]]:
    """Return DuckDB column names and primary key flags for the given table."""

    pragma_rows = connection.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return [(str(row[1]), bool(row[5])) for row in pragma_rows]


def test_metadata_tables_match_central_schema(tmp_path):
    """Metadata tables must follow the centralized schema definitions."""

    store_module = _load_vector_store()
    conn = duckdb.connect(":memory:")
    store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=conn)

    try:
        # Explicitly rerun the guards to verify idempotency
        store._ensure_metadata_table()
        store._ensure_metadata_table()
        store._ensure_index_meta_table()
        store._ensure_index_meta_table()

        metadata_columns = _table_columns(conn, store_module.METADATA_TABLE_NAME)
        index_meta_columns = _table_columns(conn, store_module.INDEX_META_TABLE)

        expected_metadata = set(store_module.database_schema.RAG_CHUNKS_METADATA_SCHEMA.names)
        expected_index_meta = set(store_module.database_schema.RAG_INDEX_META_SCHEMA.names)

        assert {name for name, _ in metadata_columns} == expected_metadata
        assert {name for name, _ in index_meta_columns} == expected_index_meta

        metadata_primary_keys = {name for name, is_pk in metadata_columns if is_pk}
        index_meta_primary_keys = {name for name, is_pk in index_meta_columns if is_pk}

        assert metadata_primary_keys == {"path"}
        assert index_meta_primary_keys == {"index_name"}
    finally:
        store.close()


def test_metadata_round_trip(tmp_path):
    """Persisted dataset metadata should be retrievable and removable."""

    store_module = _load_vector_store()
    conn = duckdb.connect(":memory:")
    store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=conn)

    try:
        dataset_metadata = store_module.DatasetMetadata(mtime_ns=1, size=2, row_count=3)
        store._store_metadata(dataset_metadata)

        assert store._get_stored_metadata() == dataset_metadata

        store._store_metadata(None)
        assert store._get_stored_metadata() is None
    finally:
        store.close()


def test_upsert_index_meta_persists_values(tmp_path):
    """Index metadata upserts should reflect the latest configuration."""

    store_module = _load_vector_store()
    conn = duckdb.connect(":memory:")
    store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=conn)

    try:
        store._upsert_index_meta(
            mode="ann",
            row_count=ROW_COUNT,
            threshold=THRESHOLD,
            nlist=NLIST,
            embedding_dim=EMBEDDING_DIM,
        )

        row = conn.execute(
            f"SELECT mode, row_count, threshold, nlist, embedding_dim, updated_at "
            f"FROM {store_module.INDEX_META_TABLE} WHERE index_name = ?",
            [store_module.INDEX_NAME],
        ).fetchone()

        assert row is not None
        assert row[0] == "ann"
        assert row[1] == ROW_COUNT
        assert row[2] == THRESHOLD
        assert row[3] == NLIST
        assert row[4] == EMBEDDING_DIM
        assert row[5] is not None
    finally:
        store.close()


def test_search_builds_expected_sql(tmp_path, monkeypatch):
    """ANN mode should emit vss_search while exact mode falls back to cosine scans."""

    store_module = _load_vector_store()
    monkeypatch.setattr(store_module.VectorStore, "_init_vss", lambda self: True)
    monkeypatch.setattr(store_module.VectorStore, "_rebuild_index", lambda self: None)

    conn = duckdb.connect(":memory:")
    store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=conn)

    try:
        rows = [
            _vector_store_row(
                store_module,
                chunk_id="chunk-1",
                document_id="doc-1",
                chunk_index=0,
                content="hello",
                embedding=[0.0, 1.0],
                tags=["tag"],
            )
        ]
        store.add(ibis.memtable(rows, schema=store_module.VECTOR_STORE_SCHEMA))

        captured_sql: list[str] = []

        class _ConnectionProxy:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql: str, params=None):
                captured_sql.append(sql)
                if "vss_search" in sql:
                    empty = {name: [] for name in store_module.SEARCH_RESULT_SCHEMA.names}
                    empty["similarity"] = []

                    columns = [*list(empty.keys()), "similarity"]

                    class _Result:
                        description = [(name,) for name in columns]

                        def fetchall(self_inner):
                            return []

                    return _Result()

                return self._inner.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        store.conn = _ConnectionProxy(store.conn)

        store.search(query_vec=[0.0, 1.0], top_k=1, mode="ann")
        assert any("vss_search" in sql for sql in captured_sql)

        store.search(query_vec=[0.0, 1.0], top_k=1, mode="exact")
        assert any("array_cosine_similarity" in sql for sql in captured_sql)
    finally:
        store.close()


def test_ann_mode_returns_expected_results_when_vss_available(tmp_path):
    """Run an end-to-end ANN query when the VSS extension can be installed."""

    store_module = _load_vector_store()
    connection = duckdb.connect(str(tmp_path / "chunks.duckdb"))

    try:
        try:
            connection.execute("INSTALL vss")
            connection.execute("LOAD vss")
        except duckdb.Error as err:
            pytest.skip(f"DuckDB VSS extension unavailable: {err}")

        store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=connection)

        try:

            def build_row(chunk_id: str, embedding: list[float], *, chunk_index: int) -> dict:
                base = dict.fromkeys(store_module.VECTOR_STORE_SCHEMA.names)
                base.update(
                    {
                        "chunk_id": chunk_id,
                        "document_type": "post",
                        "document_id": chunk_id,
                        "chunk_index": chunk_index,
                        "content": f"content-{chunk_id}",
                        "embedding": embedding,
                        "tags": ["retrieval"],
                        "authors": ["author"],
                    }
                )
                return base

            rows = [
                build_row("chunk-1", [1.0, 0.0], chunk_index=0),
                build_row("chunk-2", [0.0, 1.0], chunk_index=1),
            ]

            table = ibis.memtable(rows, schema=store_module.VECTOR_STORE_SCHEMA)
            store.add(table)

            ann_results = store.search(query_vec=[0.0, 1.0], top_k=1, mode="ann").execute()
            exact_results = store.search(query_vec=[0.0, 1.0], top_k=1, mode="exact").execute()

            assert not ann_results.empty
            assert list(ann_results["chunk_id"]) == ["chunk-2"]
            assert list(exact_results["chunk_id"]) == ["chunk-2"]
        finally:
            store.close()
    finally:
        connection.close()


def test_search_filters_accept_temporal_inputs(tmp_path, monkeypatch):
    """Temporal filters must accept typed inputs and cross-year comparisons."""

    store_module = _load_vector_store()
    monkeypatch.setattr(store_module.VectorStore, "_init_vss", lambda self: None)
    monkeypatch.setattr(store_module.VectorStore, "_rebuild_index", lambda self: None)

    conn = duckdb.connect(":memory:")
    store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=conn)

    try:

        def build_row(chunk_id: str, embedding: list[float], **overrides) -> dict:
            base = dict.fromkeys(store_module.VECTOR_STORE_SCHEMA.names)
            base.update(
                {
                    "chunk_id": chunk_id,
                    "document_type": overrides.get("document_type", "post"),
                    "document_id": overrides.get("document_id", chunk_id),
                    "chunk_index": overrides.get("chunk_index", 0),
                    "content": overrides.get("content", chunk_id),
                    "embedding": embedding,
                    "tags": overrides.get("tags", ["tag"]),
                    "authors": overrides.get("authors", ["author"]),
                }
            )
            base.update(overrides)
            return base

        rows = [
            build_row(
                "chunk-before",
                [0.0, 1.0],
                post_date=date(2023, 12, 31),
            ),
            build_row(
                "chunk-after",
                [1.0, 0.0],
                post_date=date(2024, 1, 5),
            ),
            build_row(
                "media-jan",
                [0.8, 0.2],
                document_type="media",
                document_id="media-jan",
                media_uuid="media-jan",
                media_type="image",
                message_date=datetime(2024, 1, 1, 12, tzinfo=UTC),
                tags=[],
                authors=[],
            ),
        ]

        table = ibis.memtable(rows, schema=store_module.VECTOR_STORE_SCHEMA)
        store.add(table)

        query_vector = [1.0, 0.0]

        baseline = store.search(
            query_vec=query_vector,
            top_k=5,
            min_similarity=0.0,
            mode="exact",
        ).execute()
        assert list(baseline["chunk_id"]) == ["chunk-after", "media-jan", "chunk-before"]

        filtered_by_date = store.search(
            query_vec=query_vector,
            top_k=5,
            min_similarity=0.0,
            mode="exact",
            date_after=date(2024, 1, 1),
        ).execute()
        assert list(filtered_by_date["chunk_id"]) == ["chunk-after", "media-jan"]

        filtered_by_datetime = store.search(
            query_vec=query_vector,
            top_k=5,
            min_similarity=0.0,
            mode="exact",
            date_after=datetime(2023, 12, 31, 18, 0),
        ).execute()
        assert list(filtered_by_datetime["chunk_id"]) == ["chunk-after", "media-jan"]

        filtered_with_timezone = store.search(
            query_vec=query_vector,
            top_k=5,
            min_similarity=0.0,
            mode="exact",
            date_after="2023-12-31T23:00:00+00:00",
        ).execute()
        assert list(filtered_with_timezone["chunk_id"]) == ["chunk-after", "media-jan"]
    finally:
        store.close()
