"""High-level orchestration helpers for the refactored local pipeline."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

import polars as pl
from polars.exceptions import NoDataError

from .ingest.anonymizer import Anonymizer
from .config import PipelineConfig
from .embed.embed import GeminiEmbedder
from .generate.core import RAGClient, RAGSearchResult
from .ingest.main import ingest_zip
from .rag_context.duckdb_setup import DuckDBIndex, initialise_vector_store


class LocalRAGClient(RAGClient):
    """RAG client that embeds queries locally and uses DuckDB for search."""

    def __init__(
        self,
        index: DuckDBIndex,
        *,
        embedder: GeminiEmbedder,
        text_column: str = "message",
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._text_column = text_column

    def search(
        self,
        query: str,
        *,
        top_k: int,
        min_similarity: float | None = None,
    ) -> RAGSearchResult:
        vector = self._embedder.embed_text(query)
        if not vector:
            return RAGSearchResult(snippets=[], records=[])

        frame = self._index.query_similar(
            vector,
            limit=max(int(top_k), 1),
            min_similarity=float(min_similarity) if min_similarity is not None else 0.0,
        )

        snippets: list[str] = []
        if not frame.is_empty() and self._text_column in frame.columns:
            snippets = [str(value) for value in frame.get_column(self._text_column).to_list() if value]

        filtered = frame.drop(self._index.vector_column) if self._index.vector_column in frame.columns else frame
        return RAGSearchResult(
            snippets=snippets,
            records=filtered.to_dicts() if not filtered.is_empty() else [],
        )


def ingest_exports(zip_paths: Sequence[Path]) -> pl.DataFrame:
    """Parse and concatenate WhatsApp exports into a single DataFrame."""

    frames: list[pl.DataFrame] = []
    for zip_path in zip_paths:
        frame = ingest_zip(zip_path)
        if not frame.is_empty():
            frames.append(frame)

    if not frames:
        return pl.DataFrame()

    combined = pl.concat(frames).sort("timestamp")
    return combined


def anonymise_frame(frame: pl.DataFrame, config: PipelineConfig) -> pl.DataFrame:
    """Return *frame* with deterministic pseudonyms applied when enabled."""

    if frame.is_empty() or not config.anonymization.enabled:
        return frame

    return Anonymizer.anonymize_dataframe(
        frame,
        column="author",
        target_column="anon_author",
        format=config.anonymization.output_format,
    )


def filter_by_window(
    frame: pl.DataFrame,
    *,
    days: int | None = None,
    start: date | None = None,
    end: date | None = None,
) -> pl.DataFrame:
    """Filter *frame* by the requested date constraints."""

    if frame.is_empty() or "date" not in frame.columns:
        return frame

    result = frame

    if start is not None:
        result = result.filter(pl.col("date") >= pl.lit(start))
    if end is not None:
        result = result.filter(pl.col("date") <= pl.lit(end))

    if days is not None and days > 0 and not result.is_empty():
        try:
            max_date = result.get_column("date").max()
        except NoDataError:  # pragma: no cover - defensive guard
            return result

        if isinstance(max_date, date):
            limit = max_date - timedelta(days=days - 1)
        else:
            limit = date.fromisoformat(str(max_date)) - timedelta(days=days - 1)

        result = result.filter(pl.col("date") >= pl.lit(limit))

    return result.sort("timestamp")


def determine_identity(frame: pl.DataFrame, config: PipelineConfig) -> tuple[str, str]:
    """Derive group name and slug when they are not explicitly configured."""

    def _pick(column: str, fallback: str) -> str:
        if column in frame.columns:
            for value in frame.get_column(column).to_list():
                if value:
                    return str(value)
        return fallback

    name = config.group_name or _pick("group_name", "Egregora")
    slug = config.group_slug or _derive_slug(name)
    return name, slug


def _derive_slug(name: str) -> str:
    cleaned = "".join(char if char.isalnum() else "-" for char in name.lower())
    return "-".join(part for part in cleaned.split("-") if part) or "egregora"


def embed_dataframe(
    frame: pl.DataFrame,
    config: PipelineConfig,
    *,
    embedder: GeminiEmbedder | None = None,
) -> tuple[pl.DataFrame, GeminiEmbedder]:
    """Populate the configured vector column using Gemini embeddings."""

    embed_config = config.embed
    if embedder is None:
        embedder = GeminiEmbedder(
            model=embed_config.model,
            batch_size=embed_config.batch_size,
            max_input_chars=embed_config.chunk_char_limit,
        )

    vectorised = embedder.embed_dataframe(
        frame,
        text_column=embed_config.text_column,
        vector_column=embed_config.vector_column,
    )
    return vectorised, embedder


def persist_dataframe(frame: pl.DataFrame, path: Path) -> Path:
    """Write *frame* as Parquet to *path* and return the resolved location."""

    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)
    return path.resolve()


def build_local_rag_client(
    embeddings_path: Path,
    *,
    config: PipelineConfig,
    embedder: GeminiEmbedder,
) -> LocalRAGClient:
    """Initialise a DuckDB-backed RAG client using the generated embeddings."""

    index = initialise_vector_store(
        embeddings_path,
        table_name="posts",
        vector_column=config.embed.vector_column,
        text_column=config.embed.text_column,
        install_vss=True,
    )
    return LocalRAGClient(index, embedder=embedder, text_column=config.embed.text_column)


__all__ = [
    "LocalRAGClient",
    "anonymise_frame",
    "build_local_rag_client",
    "determine_identity",
    "embed_dataframe",
    "filter_by_window",
    "ingest_exports",
    "persist_dataframe",
]
