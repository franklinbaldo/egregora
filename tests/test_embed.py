from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pytest
from typer.testing import CliRunner

from egregora.embed.cli import embed_app
from egregora.embed.embed import GeminiEmbedder


class _FakeModels:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._counter = 0

    def embed_content(self, *, model: str, content: str):  # noqa: D401
        """Mimic ``google.genai`` returning predictable vectors."""

        self.calls.append(content)
        self._counter += 1
        base = float(self._counter)
        return SimpleNamespace(embedding=[base, base + 0.5])


class _FakeClient:
    def __init__(self) -> None:
        self.models = _FakeModels()


def test_embedder_chunks_and_averages() -> None:
    client = _FakeClient()
    embedder = GeminiEmbedder(client=client, max_input_chars=4)

    vector = embedder.embed_text("abcdefghij")

    # Expect three chunks -> averaged vectors across calls [1.0, 1.5], [2.0, 2.5], [3.0, 3.5]
    assert pytest.approx(vector) == [2.0, 2.5]
    assert len(client.models.calls) == 3


def test_embed_dataframe_adds_vector_column() -> None:
    client = _FakeClient()
    embedder = GeminiEmbedder(client=client)

    frame = pl.DataFrame({"message": ["hello", "world"]})
    embedded = embedder.embed_dataframe(frame)

    assert "vector" in embedded.columns
    assert embedded.schema["vector"] == pl.List(pl.Float64)
    assert len(embedded.get_column("vector")[0]) == 2
    assert len(client.models.calls) == 2


def test_cli_writes_parquet(tmp_path, monkeypatch) -> None:
    frame = pl.DataFrame({"message": ["olá"]})
    input_path = tmp_path / "frame.parquet"
    output_path = tmp_path / "embeddings.parquet"
    frame.write_parquet(input_path)

    class _StubEmbedder:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def embed_dataframe(self, frame: pl.DataFrame, *, text_column: str = "message", vector_column: str = "vector"):
            assert text_column == "message"
            series = pl.Series(vector_column, [[0.1, 0.2] for _ in range(frame.height)], dtype=pl.List(pl.Float64))
            return frame.with_columns(series)

    monkeypatch.setattr("egregora.embed.cli.GeminiEmbedder", _StubEmbedder)

    runner = CliRunner()
    result = runner.invoke(
        embed_app,
        [str(input_path), "--output", str(output_path), "--vector-column", "embedding"],
    )

    assert result.exit_code == 0, result.output
    generated = pl.read_parquet(output_path)
    assert "embedding" in generated.columns
    assert generated.schema["embedding"] == pl.List(pl.Float64)
