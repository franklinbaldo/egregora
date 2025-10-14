from datetime import date, datetime
from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from egregora.__main__ import app
from egregora.generate.core import RAGSearchResult


class _StubEmbedder:
    def embed_text(self, _text: str) -> list[float]:
        return [0.1, 0.1]


class _StubRAGClient:
    def search(self, query: str, *, top_k: int, min_similarity: float | None = None) -> RAGSearchResult:
        return RAGSearchResult(
            snippets=[f"Contexto para {query}"],
            records=[{"message": "Contexto", "similarity": 0.9, "top_k": top_k, "min": min_similarity}],
        )


def test_pipeline_command_runs_end_to_end(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    frame = pl.DataFrame(
        {
            "timestamp": [datetime(2025, 1, 1, 9, 0)],
            "date": [date(2025, 1, 1)],
            "author": ["Alice"],
            "message": ["Bom dia"],
            "group_name": ["Grupo Teste"],
            "group_slug": ["grupo-teste"],
        }
    )

    monkeypatch.setattr("egregora.__main__.ingest_exports", lambda _paths: frame)
    monkeypatch.setattr(
        "egregora.__main__.embed_dataframe",
        lambda input_frame, _config: (
            input_frame.with_columns(
                pl.Series("vector", [[0.1, 0.1] for _ in range(input_frame.height)], dtype=pl.List(pl.Float64))
            ),
            _StubEmbedder(),
        ),
    )
    def _fake_build_local_rag_client(_path: Path, *, config, embedder):  # type: ignore[no-untyped-def]
        return _StubRAGClient()

    monkeypatch.setattr("egregora.__main__.build_local_rag_client", _fake_build_local_rag_client)

    calls: dict[str, object] = {}

    def _fake_run_generation(dataset_path: Path, **kwargs) -> None:
        calls["dataset_path"] = dataset_path
        calls["kwargs"] = kwargs

    monkeypatch.setattr("egregora.__main__._run_generation", _fake_run_generation)

    dataset_out = tmp_path / "dataset.parquet"
    result = runner.invoke(
        app,
        [
            "pipeline",
            str(tmp_path / "chat.zip"),
            "--workspace",
            str(tmp_path),
            "--dataset-out",
            str(dataset_out),
            "--show",
        ],
    )

    assert result.exit_code == 0
    assert calls["dataset_path"] == dataset_out
    kwargs = calls["kwargs"]
    assert isinstance(kwargs["rag_client"], _StubRAGClient)
    assert kwargs["group_name"] == "Grupo Teste"
    assert kwargs["group_slug"] == "grupo-teste"


