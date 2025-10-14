from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl
from hypothesis import given, strategies as st
from egregora.config import PipelineConfig
from egregora.pipeline_runner import (
    LocalRAGClient,
    anonymise_frame,
    determine_identity,
    embed_dataframe,
    filter_by_window,
    persist_dataframe,
)


class _StubEmbedder:
    def __init__(self) -> None:
        self.calls: list[pl.DataFrame] = []

    def embed_dataframe(
        self,
        frame: pl.DataFrame,
        *,
        text_column: str,
        vector_column: str,
    ) -> pl.DataFrame:
        self.calls.append(frame)
        return frame.with_columns(
            pl.lit([[0.1, 0.2]] * frame.height).alias(vector_column)
        )


class _StubIndex:
    vector_column = "vector"

    def __init__(self, frame: pl.DataFrame) -> None:
        self._frame = frame
        self.last_query: dict[str, object] | None = None

    def query_similar(
        self,
        query_vector: list[float],
        *,
        limit: int,
        min_similarity: float,
    ) -> pl.DataFrame:
        self.last_query = {
            "vector": query_vector,
            "limit": limit,
            "min_similarity": min_similarity,
        }
        return self._frame


def _make_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [datetime(2025, 1, 1, 9, 0), datetime(2025, 1, 3, 10, 0)],
            "date": [date(2025, 1, 1), date(2025, 1, 3)],
            "author": ["Alice", "Bob"],
            "message": ["Bom dia", "Resumo"],
        }
    )


def test_filter_by_window_limits_days() -> None:
    frame = _make_frame()
    filtered = filter_by_window(frame, days=1)
    assert filtered.height == 1
    assert filtered.get_column("date")[0] == date(2025, 1, 3)


def test_filter_by_window_range() -> None:
    frame = _make_frame()
    filtered = filter_by_window(frame, start=date(2025, 1, 2), end=date(2025, 1, 2))
    assert filtered.is_empty()


def test_anonymise_and_determine_identity_roundtrip() -> None:
    config = PipelineConfig()
    frame = _make_frame()
    anonymised = anonymise_frame(frame, config)
    assert "anon_author" in anonymised.columns
    name, slug = determine_identity(
        anonymised.with_columns(pl.lit("Grupo").alias("group_name")),
        config,
    )
    assert name == "Grupo"
    assert slug == "grupo"


def test_embed_dataframe_uses_existing_embedder() -> None:
    stub = _StubEmbedder()
    frame = _make_frame()
    vectorised, returned = embed_dataframe(frame, PipelineConfig(), embedder=stub)  # type: ignore[arg-type]
    assert returned is stub
    assert "vector" in vectorised.columns
    assert stub.calls[0].shape == frame.shape


def test_local_rag_client_returns_snippets() -> None:
    frame = pl.DataFrame(
        {
            "message": ["Histórico"],
            "vector": [[0.1, 0.2]],
            "similarity": [0.9],
        }
    )
    index = _StubIndex(frame)

    class _QueryEmbedder:
        def embed_text(self, text: str) -> list[float]:
            return [len(text), 1.0]

    client = LocalRAGClient(index, embedder=_QueryEmbedder(), text_column="message")
    result = client.search("teste", top_k=2, min_similarity=0.5)

    assert result.snippets == ["Histórico"]
    assert result.records[0]["similarity"] == 0.9
    assert index.last_query == {
        "vector": [5, 1.0],
        "limit": 2,
        "min_similarity": 0.5,
    }


def test_persist_dataframe_creates_file(tmp_path: Path) -> None:
    frame = _make_frame()
    output = tmp_path / "dataset.parquet"
    persisted = persist_dataframe(frame, output)
    assert persisted == output
    assert output.exists()
    assert pl.read_parquet(output).shape == frame.shape


@given(
    st.lists(
        st.dates(min_value=date(2024, 1, 1), max_value=date(2025, 12, 31)),
        min_size=1,
        max_size=12,
    ),
    st.integers(min_value=1, max_value=5),
)
def test_filter_by_window_never_expands_results(dates: list[date], days: int) -> None:
    timestamps = [datetime.combine(value, datetime.min.time()) for value in dates]
    frame = pl.DataFrame(
        {
            "timestamp": timestamps,
            "date": dates,
            "author": [f"User {idx}" for idx in range(len(dates))],
            "message": [f"Mensagem {idx}" for idx in range(len(dates))],
        }
    )

    start = min(dates)
    end = max(dates)

    bounded = filter_by_window(frame, start=start, end=end)
    assert all(start <= value <= end for value in bounded.get_column("date"))

    limited = filter_by_window(frame, days=days)
    if limited.is_empty():
        return

    newest = max(frame.get_column("date"))
    expected_floor = newest - timedelta(days=days - 1)
    assert all(value >= expected_floor for value in limited.get_column("date"))
