"""DuckDB + Ibis setup utilities for the FastMCP RAG layer."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import duckdb
import ibis
import polars as pl

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DuckDBIndex:
    """In-memory DuckDB table backed by a Parquet file with vector search helpers."""

    connection: duckdb.DuckDBPyConnection
    ibis_connection: ibis.BaseBackend | None
    table_name: str
    vector_column: str
    text_column: str
    vss_enabled: bool

    def query_similar(
        self,
        query_vector: Sequence[float],
        *,
        limit: int = 3,
        min_similarity: float = 0.0,
    ) -> pl.DataFrame:
        """Return the most similar rows to ``query_vector`` ordered by cosine similarity."""

        if not query_vector:
            return pl.DataFrame()

        if self.vss_enabled:
            frame = _query_with_vss(
                self.connection,
                self.table_name,
                self.vector_column,
                query_vector,
                limit,
            )
        else:
            frame = _query_with_fallback(
                self.connection,
                self.table_name,
                self.vector_column,
                query_vector,
                limit,
            )

        if frame.is_empty():
            return frame

        if min_similarity > 0:
            frame = frame.filter(pl.col("similarity") >= float(min_similarity))
        return frame


def initialise_vector_store(
    parquet_path: str | Path,
    *,
    table_name: str = "posts",
    vector_column: str = "vector",
    text_column: str = "message",
    install_vss: bool = True,
) -> DuckDBIndex:
    """Load a Parquet dataset into DuckDB and optionally create a VSS index."""

    dataset_path = Path(parquet_path)
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Arquivo Parquet '{dataset_path}' não encontrado para inicializar o RAG."
        )

    connection = duckdb.connect(database=":memory:")
    vss_enabled = _ensure_vss_loaded(connection) if install_vss else False

    connection.execute(
        f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet(?)",
        [str(dataset_path)],
    )

    columns = {
        row[1]: row[2] for row in connection.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    }
    if vector_column not in columns:
        raise ValueError(
            f"A coluna vetorial '{vector_column}' não existe na tabela '{table_name}'."
        )
    if text_column not in columns:
        LOGGER.warning(
            "Coluna de texto '%s' não encontrada; respostas do RAG omitirão snippets.",
            text_column,
        )

    if vss_enabled:
        try:
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS {table_name}_{vector_column}_idx "
                f"ON {table_name} USING HNSW({vector_column}) WITH (metric='cosine')"
            )
        except duckdb.Error as exc:  # pragma: no cover - defensive guard
            LOGGER.warning("Falha ao criar índice HNSW; usando fallback Python. Detalhes: %s", exc)
            vss_enabled = False

    try:
        ibis_connection = ibis.duckdb.connect(con=connection)
    except Exception as exc:  # pragma: no cover - depends on duckdb build
        LOGGER.warning(
            "Falha ao inicializar backend Ibis/DuckDB (%s); prosseguindo sem camada declarativa.",
            exc,
        )
        ibis_connection = None
    return DuckDBIndex(
        connection=connection,
        ibis_connection=ibis_connection,
        table_name=table_name,
        vector_column=vector_column,
        text_column=text_column,
        vss_enabled=vss_enabled,
    )


def _ensure_vss_loaded(connection: duckdb.DuckDBPyConnection) -> bool:
    """Attempt to install and load the DuckDB VSS extension, returning success."""

    try:
        connection.execute("INSTALL 'vss'")
        connection.execute("LOAD 'vss'")
        return True
    except duckdb.Error as exc:
        LOGGER.warning(
            "Extensão 'vss' indisponível (%s); o servidor usará cálculo de similaridade em Python.",
            exc,
        )
        return False


def _query_with_vss(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    vector_column: str,
    query_vector: Sequence[float],
    limit: int,
) -> pl.DataFrame:
    """Execute a cosine similarity query using DuckDB's VSS extension."""

    return connection.execute(
        (
            f"SELECT *, vector_cosine_similarity({vector_column}, ?) AS similarity "
            f"FROM {table_name} ORDER BY similarity DESC LIMIT ?"
        ),
        [list(map(float, query_vector)), int(limit)],
    ).pl()


def _query_with_fallback(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    vector_column: str,
    query_vector: Sequence[float],
    limit: int,
) -> pl.DataFrame:
    """Fallback similarity computation executed via Polars when VSS is unavailable."""

    frame = connection.execute(f"SELECT * FROM {table_name}").pl()
    if frame.is_empty():
        return frame

    query = [float(value) for value in query_vector]
    vectors = frame.get_column(vector_column).to_list()
    similarities = [
        _cosine_similarity(vector, query) if vector else 0.0
        for vector in vectors
    ]
    enriched = frame.with_columns(pl.Series("similarity", similarities))
    return enriched.sort("similarity", descending=True).head(limit)


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute cosine similarity between two vectors."""

    if len(a) != len(b):
        raise ValueError("Os vetores devem ter o mesmo tamanho para cálculo de similaridade.")

    dot_product = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for value_a, value_b in zip(a, b):
        dot_product += float(value_a) * float(value_b)
        norm_a += float(value_a) ** 2
        norm_b += float(value_b) ** 2

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))


__all__ = ["DuckDBIndex", "initialise_vector_store"]
