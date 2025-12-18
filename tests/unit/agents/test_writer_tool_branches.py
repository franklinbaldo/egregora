from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry

from egregora.agents.types import WriterDeps, WriterResources
from egregora.agents.writer_tools import search_media_impl


def make_resources(tmp_path: Path) -> WriterResources:
    return WriterResources(
        output=SimpleNamespace(),
        annotations_store=None,
        storage=None,
        embedding_model="test-model",
        retrieval_config=SimpleNamespace(),
        profiles_dir=tmp_path,
        journal_dir=tmp_path,
        prompts_dir=None,
        client=None,
        usage=None,
        task_store=None,
        output_registry=None,
        run_id=None,
        quota=None,
    )


def make_deps(tmp_path: Path) -> WriterDeps:
    now = datetime.utcnow()
    return WriterDeps(
        resources=make_resources(tmp_path),
        window_start=now - timedelta(hours=1),
        window_end=now,
        window_label="window-1h",
        model_name="test-model",
    )


def test_writer_deps_handles_invalid_search(monkeypatch, tmp_path):
    deps = make_deps(tmp_path)

    monkeypatch.setattr("egregora.agents.types.search", lambda request: (_ for _ in ()).throw(ValueError("bad query")))

    result = deps.search_media("bad query")

    assert result.results == []


def test_search_media_impl_raises_model_retry(monkeypatch):
    monkeypatch.setattr(
        "egregora.agents.writer_tools.search",
        lambda request: (_ for _ in ()).throw(ConnectionError("backend down")),
    )

    with pytest.raises(ModelRetry):
        search_media_impl("any")
