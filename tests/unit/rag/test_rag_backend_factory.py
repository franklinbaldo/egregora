from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock

import pytest

# Provide lightweight stubs so rag imports don't pull heavy optional deps.
if "lance_namespace" not in sys.modules:
    sys.modules["lance_namespace"] = types.SimpleNamespace()

if "lancedb.pydantic" not in sys.modules:
    lancedb_pydantic = types.ModuleType("lancedb.pydantic")
    lancedb_pydantic.LanceModel = type("LanceModel", (), {})
    lancedb_pydantic.Vector = lambda _dim: list[float]
    sys.modules["lancedb.pydantic"] = lancedb_pydantic

if "lancedb" not in sys.modules:
    lancedb_module = types.ModuleType("lancedb")

    class _DummyTable:
        pass

    def _connect(_path: str) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            table_names=list,
            create_table=lambda *args, **kwargs: _DummyTable(),
            open_table=lambda _name: _DummyTable(),
        )

    lancedb_module.connect = _connect
    sys.modules["lancedb"] = lancedb_module

from egregora import rag
from egregora.config.settings import EgregoraConfig


def test_embed_fn_uses_rag_settings_for_router(monkeypatch: pytest.MonkeyPatch) -> None:
    """Embedding router should be constructed with configured RAG settings."""

    config = EgregoraConfig()
    config.rag.embedding_max_batch_size = 7
    config.rag.embedding_timeout = 3.5
    config.models.embedding = "models/test-embedding"

    monkeypatch.setattr(rag, "load_egregora_config", lambda _path: config)

    created_router = AsyncMock()
    created_router.embed = AsyncMock(return_value=[[0.1]])

    create_router_mock = AsyncMock(return_value=created_router)
    monkeypatch.setattr(rag, "create_embedding_router", create_router_mock)

    embed_texts_mock = AsyncMock(return_value=[[0.1]])
    monkeypatch.setattr(rag, "embed_texts_async", embed_texts_mock)

    class DummyBackend:
        def __init__(self, *, embed_fn, **_: object) -> None:
            self.embed_fn = embed_fn

    monkeypatch.setattr(rag, "LanceDBRAGBackend", DummyBackend)

    backend = rag._create_backend()

    asyncio.run(backend.embed_fn(["hello"], "RETRIEVAL_DOCUMENT"))

    create_router_mock.assert_awaited_once_with(
        model="models/test-embedding",
        api_key=None,
        max_batch_size=7,
        timeout=3.5,
    )
    embed_texts_mock.assert_awaited_once_with(
        ["hello"], task_type="RETRIEVAL_DOCUMENT", router=created_router
    )
