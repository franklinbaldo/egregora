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

    other_backend = ibis.duckdb.connect()
    previous_backend = ibis.get_backend()
    ibis.set_backend(other_backend)

    try:
        store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=duckdb.connect(":memory:"))
        try:
            base_rows = [
                {
                    "chunk_id": "chunk-1",
                    "document_type": "post",
                    "document_id": "doc-1",
                    "chunk_index": 0,
                    "content": "hello",
                    "embedding": [0.0, 1.0],
                    "tags": ["tag"],
                }
            ]
            first_batch = ibis.memtable(base_rows)
            store.add(first_batch)

            second_batch = ibis.memtable(
                [
                    {
                        "chunk_id": "chunk-2",
                        "document_type": "post",
                        "document_id": "doc-2",
                        "chunk_index": 0,
                        "content": "world",
                        "embedding": [1.0, 0.0],
                        "tags": ["tag"],
                    }
                ]
            )
            store.add(second_batch)

            stored_rows = store.get_all().order_by("chunk_id").execute()
            assert list(stored_rows["chunk_id"]) == ["chunk-1", "chunk-2"]
        finally:
            store.close()
    finally:
        ibis.set_backend(previous_backend)


def test_ensure_dataset_loaded_skips_rebuild_without_changes(tmp_path, monkeypatch):
    """Consecutive ensure calls must avoid rebuilding when metadata is stable."""

    store_module = _load_vector_store()
    monkeypatch.setattr(store_module.VectorStore, "_init_vss", lambda self: None)

    rebuild_calls: list[int] = []

    def _record_rebuild(self):
        rebuild_calls.append(1)

    monkeypatch.setattr(store_module.VectorStore, "_rebuild_index", _record_rebuild)

    store = store_module.VectorStore(tmp_path / "chunks.parquet", connection=duckdb.connect(":memory:"))

    try:
        rows = [
            {
                "chunk_id": "chunk-1",
                "document_type": "post",
                "document_id": "doc-1",
                "chunk_index": 0,
                "content": "hello",
                "embedding": [0.0, 1.0],
                "tags": ["tag"],
            }
        ]
        store.add(ibis.memtable(rows, schema=store_module.VECTOR_STORE_SCHEMA))

        rebuild_calls.clear()

        store._ensure_dataset_loaded()
        assert rebuild_calls == []

        store._ensure_dataset_loaded()
        assert rebuild_calls == []

        store._ensure_dataset_loaded(force=True)
        assert rebuild_calls == [1]

        metadata_row = store.conn.execute(
            "SELECT row_count FROM rag_chunks_metadata WHERE path = ?",
            [str(tmp_path / "chunks.parquet")],
        ).fetchone()

        assert metadata_row is not None
        assert metadata_row[0] == 1
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
            {
                "chunk_id": "chunk-1",
                "document_type": "post",
                "document_id": "doc-1",
                "chunk_index": 0,
                "content": "hello",
                "embedding": [0.0, 1.0],
                "tags": ["tag"],
            }
        ]
        store.add(ibis.memtable(rows, schema=store_module.VECTOR_STORE_SCHEMA))

        captured: dict[str, str] = {}
        original_execute = store.conn.execute

        def _capture_execute(sql: str, params=None):
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

            return original_execute(sql, params)

        monkeypatch.setattr(store.conn, "execute", _capture_execute)

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


def test_rebuild_index_prefers_exact_mode_below_threshold(tmp_path, monkeypatch, caplog):
    """Small tables should keep metadata but avoid rebuilding the VSS index."""

    store_module = _load_vector_store()
    monkeypatch.setattr(store_module.VectorStore, "_init_vss", lambda self: None)

    connection = duckdb.connect(":memory:")
    store = store_module.VectorStore(
        tmp_path / "chunks.parquet",
        connection=connection,
        exact_index_threshold=10,
    )

    try:
        caplog.set_level("INFO")

        row_template = {name: None for name in store_module.VECTOR_STORE_SCHEMA.names}
        rows = []
        for idx in range(3):
            base = row_template.copy()
            base.update(
                {
                    "chunk_id": f"chunk-{idx}",
                    "document_type": "post",
                    "document_id": f"doc-{idx}",
                    "chunk_index": idx,
                    "content": f"content-{idx}",
                    "embedding": [1.0, 0.0],
                    "tags": ["tag"],
                }
            )
            rows.append(base)

        store.add(ibis.memtable(rows, schema=store_module.VECTOR_STORE_SCHEMA))

        meta = connection.execute(
            "SELECT mode, nlist FROM index_meta WHERE index_name = ?",
            [store_module.INDEX_NAME],
        ).fetchone()

        assert meta == ("exact", None)

        index_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM duckdb_indexes()
            WHERE lower(index_name) = lower(?)
            """,
            [store_module.INDEX_NAME],
        ).fetchone()[0]

        assert index_count == 0
        assert any("exact similarity scan" in message for message in caplog.messages)
    finally:
        store.close()
        connection.close()


def test_rebuild_index_uses_ivfflat_above_threshold(tmp_path, caplog):
    """Large tables should build a VSS IVFFLAT index and persist its parameters."""

    store_module = _load_vector_store()
    connection = duckdb.connect(str(tmp_path / "chunks.duckdb"))

    store = None
    try:
        try:
            connection.execute("INSTALL vss")
            connection.execute("LOAD vss")
        except duckdb.Error as err:
            pytest.skip(f"DuckDB VSS extension unavailable: {err}")

        store = store_module.VectorStore(
            tmp_path / "chunks.parquet",
            connection=connection,
            exact_index_threshold=1,
        )

        caplog.set_level("INFO")

        row_template = {name: None for name in store_module.VECTOR_STORE_SCHEMA.names}
        rows = []
        for idx in range(4):
            base = row_template.copy()
            base.update(
                {
                    "chunk_id": f"chunk-{idx}",
                    "document_type": "post",
                    "document_id": f"doc-{idx}",
                    "chunk_index": idx,
                    "content": f"content-{idx}",
                    "embedding": [float(idx), float(idx + 1)],
                    "tags": ["tag"],
                }
            )
            rows.append(base)

        store.add(ibis.memtable(rows, schema=store_module.VECTOR_STORE_SCHEMA))

        meta = connection.execute(
            "SELECT mode, nlist FROM index_meta WHERE index_name = ?",
            [store_module.INDEX_NAME],
        ).fetchone()

        assert meta is not None
        mode, nlist = meta
        assert mode == "ann"
        assert nlist and nlist >= 1

        index_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM duckdb_indexes()
            WHERE lower(index_name) = lower(?)
            """,
            [store_module.INDEX_NAME],
        ).fetchone()[0]

        assert index_count == 1
        assert any("IVFFLAT" in message for message in caplog.messages)
    finally:
        if store is not None:
            store.close()
        connection.close()
