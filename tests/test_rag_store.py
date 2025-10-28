"""Regression tests for the RAG vector store."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import duckdb

import ibis


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
