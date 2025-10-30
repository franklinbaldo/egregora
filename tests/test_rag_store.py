"""Regression tests for the RAG vector store."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import ibis
import pyarrow as pa
import pytest


def _vector_store_row(store_module, **overrides):
    """Construct a row matching VECTOR_STORE_SCHEMA with sensible defaults."""

    base = {name: None for name in store_module.VECTOR_STORE_SCHEMA.names}

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
    from egregora.knowledge.rag import store
    return store


def test_search_builds_expected_sql(tmp_path, monkeypatch):
    """ANN mode should emit vss_search while exact mode falls back to cosine scans."""

    store_module = _load_vector_store()
    monkeypatch.setattr(store_module.VectorStore, "_init_vss", lambda self: None)
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

        captured: dict[str, str] = {}

        class _ConnectionProxy:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql: str, params=None):
                captured["sql"] = sql
                if "vss_search" in sql:
                    empty = {
                        name: []
                        for name in store_module.SEARCH_RESULT_SCHEMA.names
                    }
                    empty["similarity"] = []

                    class _Result:
                        def arrow(self_inner):
                            return pa.table(empty)

                    return _Result()

                return self._inner.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        store.conn = _ConnectionProxy(store.conn)

        store.search(query_vec=[0.0, 1.0], top_k=1, mode="ann")
        assert "vss_search" in captured["sql"]

        store.search(query_vec=[0.0, 1.0], top_k=1, mode="exact")
        assert "array_cosine_similarity" in captured["sql"]
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
                base = {name: None for name in store_module.VECTOR_STORE_SCHEMA.names}
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
            base = {name: None for name in store_module.VECTOR_STORE_SCHEMA.names}
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

        baseline = (
            store.search(
                query_vec=query_vector,
                top_k=5,
                min_similarity=0.0,
                mode="exact",
            )
            .execute()
        )
        assert list(baseline["chunk_id"]) == ["chunk-after", "media-jan", "chunk-before"]

        filtered_by_date = (
            store.search(
                query_vec=query_vector,
                top_k=5,
                min_similarity=0.0,
                mode="exact",
                date_after=date(2024, 1, 1),
            )
            .execute()
        )
        assert list(filtered_by_date["chunk_id"]) == ["chunk-after", "media-jan"]

        filtered_by_datetime = (
            store.search(
                query_vec=query_vector,
                top_k=5,
                min_similarity=0.0,
                mode="exact",
                date_after=datetime(2023, 12, 31, 18, 0),
            )
            .execute()
        )
        assert list(filtered_by_datetime["chunk_id"]) == ["chunk-after", "media-jan"]

        filtered_with_timezone = (
            store.search(
                query_vec=query_vector,
                top_k=5,
                min_similarity=0.0,
                mode="exact",
                date_after="2023-12-31T23:00:00+00:00",
            )
            .execute()
        )
        assert list(filtered_with_timezone["chunk_id"]) == ["chunk-after", "media-jan"]
    finally:
        store.close()
