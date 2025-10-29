"""Regression tests for the RAG vector store."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import duckdb
import ibis
import pyarrow as pa
import pytest


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
    """Load the vector store module directly to avoid heavy package imports."""

    module_path = Path(__file__).resolve().parents[1] / "src" / "egregora" / "rag" / "store.py"
    spec = importlib.util.spec_from_file_location("egregora_rag_store", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load vector store module for testing")

    existing = sys.modules.get("egregora_rag_store")
    if existing is not None:
        return existing

    module = importlib.util.module_from_spec(spec)
    sys.modules["egregora_rag_store"] = module
    spec.loader.exec_module(module)
    return module


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

            table = ibis.memtable(rows)
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


def _vector_store_row(module, **overrides):
    """Create a fully-specified row for the vector store schema."""

    base = {name: None for name in module.VECTOR_STORE_SCHEMA.names}
    base.update(
        {
            "chunk_id": "chunk",
            "document_type": "post",
            "document_id": "chunk",
            "chunk_index": 0,
            "content": "",
            "embedding": [],
            "tags": [],
            "authors": [],
        }
    )
    base.update(overrides)
    return base
