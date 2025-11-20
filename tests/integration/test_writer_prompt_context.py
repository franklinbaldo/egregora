"""Integration-level regression coverage for writer prompt context."""

from __future__ import annotations

from types import SimpleNamespace

from egregora.agents.writer import writer_runner


class DummyTable:
    """Minimal table stub that satisfies the writer prompt helper contract."""

    def to_pyarrow(self):
        return "pyarrow-table"


def test_writer_prompt_context_passes_storage_to_rag(monkeypatch, tmp_path):
    """Ensure the writer prompt context hands the DuckDB storage handle to the RAG helper."""

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        writer_runner,
        "_build_conversation_markdown_table",
        lambda *args, **kwargs: "conversation-md",
    )
    monkeypatch.setattr(writer_runner, "_load_profiles_context", lambda *args, **kwargs: "profiles")
    monkeypatch.setattr(writer_runner, "_load_journal_memory", lambda *args, **kwargs: "journal")
    monkeypatch.setattr(writer_runner, "get_active_authors", lambda *args, **kwargs: ["alice"])

    def fake_build_rag_context(conversation, store, client, **kwargs):
        captured["conversation"] = conversation
        captured["store"] = store
        captured["storage"] = kwargs["storage"]
        return "rag-context"

    monkeypatch.setattr(writer_runner, "build_rag_context_for_prompt", fake_build_rag_context)

    rag_store = SimpleNamespace(parquet_path=tmp_path / "chunks.parquet")
    storage = object()
    ctx = SimpleNamespace(
        enable_rag=True,
        rag_store=rag_store,
        client="dummy-client",
        embedding_model="models/embedding",
        retrieval_mode="ann",
        retrieval_nprobe=None,
        retrieval_overfetch=None,
        storage=storage,
        profiles_dir=tmp_path,
        output_dir=tmp_path,
        annotations_store=None,
    )

    result = writer_runner._build_writer_prompt_context(DummyTable(), ctx)

    assert captured["storage"] is storage
    assert captured["store"] is rag_store
    assert result.rag_context == "rag-context"
    assert result.conversation_md == "conversation-md"
    assert result.profiles_context == "profiles"
    assert result.journal_memory == "journal"
    assert result.active_authors == ["alice"]
