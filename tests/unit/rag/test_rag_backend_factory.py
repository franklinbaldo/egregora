from __future__ import annotations

import sys
import types
from unittest.mock import Mock

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

from typing import TYPE_CHECKING

from egregora import config as egregora_config
from egregora import rag

if TYPE_CHECKING:
    import pytest


def test_embed_fn_uses_rag_settings_for_router(
    monkeypatch: pytest.MonkeyPatch,
    config_factory,  # Use factory fixture
) -> None:
    """Embedding router should be constructed with configured RAG settings via strategy pattern."""

    # Use factory to create config with specific test values
    config = config_factory(
        rag__embedding_max_batch_size=7,
        rag__embedding_timeout=3.5,
        models__embedding="models/test-embedding",
    )

    monkeypatch.setattr(egregora_config, "load_egregora_config", lambda _path=None: config)

    # Mock the strategy to verify it's called correctly
    mock_strategy = Mock()
    mock_strategy.embed.return_value = [[0.1]]

    from egregora.rag.strategies import EmbeddingProviderFactory

    factory_mock = Mock(return_value=mock_strategy)
    monkeypatch.setattr(EmbeddingProviderFactory, "create", factory_mock)

    class DummyBackend:
        def __init__(self, *, embed_fn, **_: object) -> None:
            self.embed_fn = embed_fn

    monkeypatch.setattr(rag, "LanceDBRAGBackend", DummyBackend)

    # Get backend (which will initialize with embed_fn)
    rag.get_backend()

    # Call embed_fn to trigger strategy usage
    rag.embed_fn(("hello",), "RETRIEVAL_DOCUMENT")

    # Verify factory was called with correct model
    factory_mock.assert_called_once_with("models/test-embedding")

    # Verify strategy was called with the text
    mock_strategy.embed.assert_called_once_with(["hello"], task_type="RETRIEVAL_DOCUMENT")
