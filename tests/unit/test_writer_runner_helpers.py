from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import ibis
import pandas as pd
import pytest

from egregora.agents.writer.writer_runner import (
    DocumentIndexPlan,
    WriterConfig,
    WriterEnvironment,
    WriterPromptContext,
    _build_writer_environment,
    _build_writer_prompt_context,
    _fetch_format_documents,
    _index_documents,
    _detect_changed_documents,
    _render_writer_prompt,
    _resolve_document_paths,
)
from egregora.config.settings import EgregoraConfig


class StubOutputAdapter:
    def __init__(self, table: ibis.Table) -> None:
        self._table = table

    def list_documents(self) -> ibis.Table:
        return self._table

    def resolve_document_path(self, identifier: str) -> Path:
        if identifier == "good":
            return Path("/tmp/good.md")
        raise ValueError("bad identifier")

    def get_format_instructions(self) -> str:
        return "format instructions"


class StubVectorStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def get_indexed_sources_table(self) -> ibis.Table:
        data = pd.DataFrame(
            {
                "source_path": ["/tmp/good.md"],
                "source_mtime_ns": [1],
            }
        )
        return ibis.memtable(data)


@dataclass
class StubWriterAgentContext:
    start_time: Any
    end_time: Any
    url_convention: Any
    url_context: Any
    output_format: Any
    rag_store: Any
    annotations_store: Any
    client: Any
    prompts_dir: Any


def test_fetch_format_documents_empty_returns_none() -> None:
    empty_table = ibis.memtable(
        [],
        schema={"storage_identifier": "string", "mtime_ns": "int64"},
    )
    adapter = StubOutputAdapter(empty_table)

    table, count = _fetch_format_documents(adapter)

    assert table is None
    assert count == 0


def test_fetch_format_documents_returns_table() -> None:
    table_data = ibis.memtable(
        [("doc", 1)],
        schema={"storage_identifier": "string", "mtime_ns": "int64"},
    )
    adapter = StubOutputAdapter(table_data)

    table, count = _fetch_format_documents(adapter)

    assert table is table_data
    assert count == 1


def test_resolve_document_paths_filters_invalid() -> None:
    df = pd.DataFrame({"storage_identifier": ["good", "bad"], "mtime_ns": [1, 2]})
    table = ibis.memtable(df)
    adapter = StubOutputAdapter(table)

    resolved = _resolve_document_paths(table, adapter)
    assert resolved is not None

    resolved_df = resolved.execute()
    assert resolved_df.to_dict(orient="list") == {
        "storage_identifier": ["good"],
        "mtime_ns": [1],
        "source_path": ["/tmp/good.md"],
    }


def test_detect_changed_documents_identifies_new_and_changed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "storage_identifier": ["same", "changed", "new"],
            "source_path": ["/tmp/good.md", "/tmp/good.md", "/tmp/new.md"],
            "mtime_ns": [1, 2, 3],
        }
    )
    docs_table = ibis.memtable(df)

    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.VectorStore",
        lambda path: StubVectorStore(path),
    )

    plan = _detect_changed_documents(docs_table, tmp_path, total_documents=3)

    assert isinstance(plan.store, StubVectorStore)
    assert plan.store.path == tmp_path / "chunks.parquet"
    assert plan.skipped_count == 1

    pending = plan.to_index.sort_values("storage_identifier")
    assert pending["storage_identifier"].tolist() == ["changed", "new"]


def test_index_documents_indexes_loaded_docs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "storage_identifier": ["ok", "skip"],
            "source_path": [str(tmp_path / "ok.md"), str(tmp_path / "skip.md")],
            "mtime_ns": [1, 2],
        }
    )
    plan = DocumentIndexPlan(to_index=df, store="store", total_documents=2)

    calls: list[tuple[Any, Any, dict[str, Any]]] = []
    loaded_doc = object()

    def fake_load(path: Path) -> object | None:
        return None if "skip" in path.name else loaded_doc

    def fake_index(doc: object, store: Any, **kwargs: Any) -> None:
        calls.append((doc, store, kwargs))

    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner._load_document_from_path",
        fake_load,
    )
    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.index_document",
        fake_index,
    )

    indexed_count = _index_documents(plan, embedding_model="model")

    assert indexed_count == 1
    assert len(calls) == 1
    doc, store, kwargs = calls[0]
    assert doc is loaded_doc
    assert store == "store"
    assert kwargs["embedding_model"] == "model"
    assert kwargs["source_path"] == str(tmp_path / "ok.md")
    assert kwargs["source_mtime_ns"] == 1


def test_build_writer_environment_uses_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = WriterConfig(
        output_dir=tmp_path / "output/posts",
        profiles_dir=tmp_path / "profiles",
        rag_dir=tmp_path / "rag",
        site_root=tmp_path,
        egregora_config=EgregoraConfig(),
        cli_model="cli-model",
    )

    config.egregora_config.output.format = "mkdocs"

    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.get_model_for_task",
        lambda *args, **kwargs: "embed-model",
    )

    fake_annotation_store = SimpleNamespace()
    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.AnnotationStore",
        lambda path: fake_annotation_store,
    )

    fake_output_format = SimpleNamespace(get_format_instructions=lambda: "")
    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.create_output_format",
        lambda *args, **kwargs: fake_output_format,
    )

    fake_rag_store = SimpleNamespace()
    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.VectorStore",
        lambda path: fake_rag_store,
    )

    fake_runtime_output = SimpleNamespace(url_convention="urls")
    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.MkDocsFilesystemAdapter",
        lambda **kwargs: fake_runtime_output,
    )

    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.WriterAgentContext",
        StubWriterAgentContext,
    )

    start_time = object()
    end_time = object()
    environment = _build_writer_environment(config, start_time, end_time, client=object())

    assert environment.embedding_model == "embed-model"
    assert environment.egregora_config.models.writer == "cli-model"
    assert environment.output_format is fake_output_format
    assert environment.runtime_context.output_format is fake_runtime_output
    assert environment.annotations_store is fake_annotation_store
    assert environment.rag_store is fake_rag_store


def test_build_writer_prompt_context_uses_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    config = WriterConfig()
    config.enable_rag = True
    config.rag_dir = Path("/rag")
    config.profiles_dir = Path("/profiles")
    config.retrieval_mode = "ann"
    config.retrieval_nprobe = 5
    config.retrieval_overfetch = 2

    environment = WriterEnvironment(
        writer_config=config,
        egregora_config=EgregoraConfig(),
        output_format=SimpleNamespace(get_format_instructions=lambda: ""),
        runtime_context=SimpleNamespace(prompts_dir=None),
        annotations_store=object(),
        rag_store=object(),
        embedding_model="embed",
    )

    table = SimpleNamespace(to_pyarrow=lambda: "arrow")

    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner._build_conversation_markdown",
        lambda messages, store: "conversation",
    )
    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.build_rag_context_for_prompt",
        lambda markdown, rag_dir, client, **kwargs: f"rag:{markdown}:{kwargs['embedding_model']}",
    )
    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner._load_profiles_context",
        lambda table, profiles_dir: "profiles",
    )
    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner._load_journal_memory",
        lambda rag_dir: "journal",
    )
    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.get_active_authors",
        lambda table: ["alice", "bob"],
    )

    prompt_context = _build_writer_prompt_context(table, environment, client=object())

    assert prompt_context == WriterPromptContext(
        conversation_md="conversation",
        rag_context="rag:conversation:embed",
        profiles_context="profiles",
        journal_memory="journal",
        active_authors=["alice", "bob"],
    )


def test_render_writer_prompt_uses_template(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    class StubTemplate:
        def __init__(self, **kwargs: Any) -> None:
            calls.update(kwargs)

        def render(self) -> str:
            return "rendered"

    monkeypatch.setattr(
        "egregora.agents.writer.writer_runner.WriterPromptTemplate",
        StubTemplate,
    )

    config = WriterConfig()
    egregora_config = EgregoraConfig()
    egregora_config.writer.custom_instructions = "custom"

    environment = WriterEnvironment(
        writer_config=config,
        egregora_config=egregora_config,
        output_format=SimpleNamespace(get_format_instructions=lambda: "format"),
        runtime_context=SimpleNamespace(prompts_dir=Path("/prompts")),
        annotations_store=object(),
        rag_store=object(),
        embedding_model="embed",
    )

    prompt_context = WriterPromptContext(
        conversation_md="conversation",
        rag_context="rag",
        profiles_context="profiles",
        journal_memory="journal",
        active_authors=["alice", "bob"],
    )

    rendered = _render_writer_prompt(prompt_context, environment, date_range="range")

    assert rendered == "rendered"
    assert calls == {
        "date": "range",
        "markdown_table": "conversation",
        "active_authors": "alice, bob",
        "custom_instructions": "custom",
        "format_instructions": "format",
        "profiles_context": "profiles",
        "rag_context": "rag",
        "journal_memory": "journal",
        "enable_memes": False,
        "prompts_dir": Path("/prompts"),
    }
