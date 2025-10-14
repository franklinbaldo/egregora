"""FastMCP server exposing DuckDB-backed RAG search capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl

from fastmcp.server import FastMCP

from ..embed.embed import GeminiEmbedder
from .duckdb_setup import initialise_vector_store


@dataclass(slots=True)
class SearchResponse:
    """Serializable payload returned by the FastMCP tool."""

    query: str
    k: int
    min_similarity: float
    snippets: list[str]
    results: list[dict[str, Any]]


class FastMCPRAGServer:
    """Compose Gemini embeddings, DuckDB vector queries and FastMCP."""

    def __init__(
        self,
        parquet_path: str | None = None,
        *,
        table_name: str = "posts",
        vector_column: str = "vector",
        text_column: str = "message",
        install_vss: bool = True,
        default_top_k: int = 3,
        default_min_similarity: float = 0.0,
        embedder: GeminiEmbedder | None = None,
    ) -> None:
        if parquet_path is None:
            raise ValueError("É necessário fornecer um arquivo Parquet para o servidor RAG.")

        self.index = initialise_vector_store(
            parquet_path,
            table_name=table_name,
            vector_column=vector_column,
            text_column=text_column,
            install_vss=install_vss,
        )
        self.embedder = embedder or GeminiEmbedder()
        self.default_top_k = max(int(default_top_k), 1)
        self.default_min_similarity = float(default_min_similarity)

        self._server = FastMCP(
            name="egregora-rag",
            version="0.1.0",
            instructions="Contexto histórico das conversas da Egregora disponível via FastMCP.",
        )
        self._tool = self._server.tool(
            name="search_similar",
            description=(
                "Busca mensagens similares usando embeddings Gemini e DuckDB. "
                "Retorna snippets e metadados ordenados por similaridade."
            ),
        )(self._search_tool)

    def run(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8000,
        transport: str = "http",
        show_banner: bool = True,
    ) -> None:
        """Start the FastMCP server synchronously."""

        self._server.run(transport=transport, host=host, port=port, show_banner=show_banner)

    # ------------------------------------------------------------------
    # Tool implementation
    def _search_tool(
        self,
        query: str,
        k: int | None = None,
        min_similarity: float | None = None,
    ) -> SearchResponse:
        """FastMCP tool callable that orchestrates embedding and vector search."""

        limit = max(int(k or self.default_top_k), 1)
        threshold = (
            float(min_similarity) if min_similarity is not None else self.default_min_similarity
        )

        matches = self.search(query, limit=limit, min_similarity=threshold)
        snippets = matches.get_column(self.index.text_column).to_list() if self.index.text_column in matches.columns else []
        records = _normalise_records(matches, exclude={self.index.vector_column})
        return SearchResponse(
            query=query,
            k=limit,
            min_similarity=threshold,
            snippets=snippets,
            results=records,
        )

    def search(
        self,
        query: str,
        *,
        limit: int | None = None,
        min_similarity: float | None = None,
    ) -> pl.DataFrame:
        """Execute a similarity search without going through the FastMCP transport."""

        vector = self.embedder.embed_text(query)
        if not vector:
            return pl.DataFrame()

        return self.index.query_similar(
            vector,
            limit=max(int(limit or self.default_top_k), 1),
            min_similarity=float(min_similarity) if min_similarity is not None else self.default_min_similarity,
        )


def _normalise_records(frame: pl.DataFrame, *, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    """Convert a Polars frame into serialisable dictionaries, skipping heavy columns."""

    if frame.is_empty():
        return []
    exclude = exclude or set()
    cleaned = frame.drop(list(exclude & set(frame.columns))) if exclude else frame
    return cleaned.to_dicts()


__all__ = ["FastMCPRAGServer", "SearchResponse"]
