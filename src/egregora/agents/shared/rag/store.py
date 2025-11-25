from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import ibis
import ibis.expr.datatypes as dt
import lancedb

from egregora.config import EMBEDDING_DIM
from egregora.database.duckdb_manager import DuckDBStorageManager

logger = logging.getLogger(__name__)

DEDUP_MAX_RANK = 2
DEFAULT_ANN_OVERFETCH = 5

VECTOR_COLUMNS = [
    "chunk_id",
    "document_type",
    "document_id",
    "source_path",
    "source_mtime_ns",
    "chunk_index",
    "content",
    "embedding",
    "tags",
    "category",
    "authors",
    "post_slug",
    "post_title",
    "post_date",
    "media_uuid",
    "media_type",
    "media_path",
    "original_filename",
    "message_date",
    "author_uuid",
]

VECTOR_STORE_SCHEMA = ibis.schema(
    {
        "chunk_id": dt.string,
        "document_type": dt.string,
        "document_id": dt.string,
        "source_path": dt.string,
        "source_mtime_ns": dt.int64,
        "chunk_index": dt.int64,
        "content": dt.string,
        "embedding": dt.Array(dt.float32),
        "tags": dt.Array(dt.string),
        "category": dt.string,
        "authors": dt.Array(dt.string),
        "post_slug": dt.string,
        "post_title": dt.string,
        "post_date": dt.date,
        "media_uuid": dt.string,
        "media_type": dt.string,
        "media_path": dt.string,
        "original_filename": dt.string,
        "message_date": dt.timestamp("UTC"),
        "author_uuid": dt.string,
    }
)


@dataclass(frozen=True)
class DatasetMetadata:
    """Lightweight metadata used for cache keys."""

    mtime_ns: int
    size: int
    row_count: int


class VectorStore:
    """LanceDB-backed vector store.

    This implementation intentionally mirrors the previous interface but uses LanceDB for
    storage and similarity search. The backing dataset lives at ``parquet_path`` (now
    ``.lance``) and is created on demand.
    """

    def __init__(self, parquet_path: Path, *, storage: DuckDBStorageManager | None = None) -> None:
        self.table_name = parquet_path.stem
        self.parquet_path = parquet_path.with_suffix(".lance")
        self.storage = storage  # kept for compatibility; unused with LanceDB

        self._db_path = self.parquet_path.parent
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._db_path))
        self._table = self._open_table()

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def _open_table(self):
        if self.table_name in self._db.table_names():
            return self._db.open_table(self.table_name)
        return None

    def _ensure_table(self, rows: list[dict[str, Any]]) -> None:
        if self._table is None:
            logger.info("Creating LanceDB table %s", self.table_name)
            self._table = self._db.create_table(
                self.table_name, data=rows, mode="overwrite", embedding_function=None
            )
        else:
            self._table.add(rows)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add(self, chunks_table: Any) -> None:
        """Add chunks to the vector store.

        Accepts an Ibis table or any object that can be materialized to records via
        ``to_pyarrow``/``execute``. Embedding dimensionality is validated to avoid
        index corruption.
        """
        records = self._to_records(chunks_table)
        if not records:
            logger.info("No chunks provided; skipping LanceDB add")
            return

        if "embedding" not in records[0]:
            msg = "Chunks must include an 'embedding' column"
            raise ValueError(msg)

        embeddings = [record.get("embedding") for record in records]
        self._validate_embedding_dimension(embeddings)

        normalized_records: list[dict[str, Any]] = []
        for record in records:
            normalized = {**record}
            normalized["embedding"] = list(normalized["embedding"])
            for col in VECTOR_COLUMNS:
                normalized.setdefault(col, None)
            normalized_records.append(normalized)

        ordered_records = [{col: rec[col] for col in VECTOR_COLUMNS} for rec in normalized_records]

        self._ensure_table(ordered_records)
        logger.info("Saved %s chunks to LanceDB", len(ordered_records))

    def search(  # noqa: PLR0913
        self,
        query_vec: list[float],
        top_k: int = 5,
        min_similarity_threshold: float = 0.7,
        tag_filter: list[str] | None = None,
        date_after: date | datetime | str | None = None,
        document_type: str | None = None,
        media_types: list[str] | None = None,
        *,
        mode: str = "ann",
        nprobe: int | None = None,
        overfetch: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks using LanceDB."""
        if self._table is None:
            return self._empty_results()

        fetch = overfetch if overfetch and overfetch > 1 else DEFAULT_ANN_OVERFETCH
        limit = max(top_k * fetch, top_k)

        results = (
            self._table.search(query_vec, vector_column_name="embedding")
            .metric("cosine")
            .limit(limit)
            .to_arrow()
        )
        if results.num_rows == 0:
            return self._empty_results()

        records = results.to_pylist()

        for record in records:
            if "score" in record:
                record["similarity"] = record.pop("score")
            elif "distance" in record:
                record["similarity"] = 1 - record.get("distance", 0.0)
            else:
                record.setdefault("similarity", 0.0)

        filtered = self._apply_filters(
            records,
            min_similarity_threshold=min_similarity_threshold,
            tag_filter=tag_filter,
            date_after=date_after,
            document_type=document_type,
            media_types=media_types,
        )

        filtered.sort(key=lambda row: float(row.get("similarity", 0.0)), reverse=True)
        return filtered[:top_k]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _apply_filters(
        self,
        records: list[dict[str, Any]],
        *,
        min_similarity_threshold: float,
        tag_filter: list[str] | None,
        date_after: date | datetime | str | None,
        document_type: str | None,
        media_types: list[str] | None,
    ) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        normalized_date = self._normalize_date_filter(date_after) if date_after is not None else None

        for record in records:
            similarity = float(record.get("similarity", 0.0))
            if similarity < min_similarity_threshold:
                continue
            if document_type and record.get("document_type") != document_type:
                continue
            if media_types and record.get("media_type") not in media_types:
                continue
            if tag_filter:
                tags = record.get("tags") or []
                if not set(tags) & set(tag_filter):
                    continue
            if normalized_date is not None:
                post_date = record.get("post_date")
                if not self._is_after(post_date, normalized_date):
                    continue
            filtered.append(record)

        return filtered

    @staticmethod
    def _is_after(value: Any, threshold: datetime) -> bool:
        if value is None:
            return False
        if isinstance(value, datetime):
            return value >= threshold
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time(), tzinfo=threshold.tzinfo) >= threshold
        return False

    @staticmethod
    def _normalize_date_filter(value: date | datetime | str) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        return datetime.fromisoformat(value)

    @staticmethod
    def _to_records(table: Any) -> list[dict[str, Any]]:
        if table is None:
            return []
        if hasattr(table, "to_pyarrow"):
            return table.to_pyarrow().to_pylist()
        if hasattr(table, "execute"):
            result = table.execute()
            if hasattr(result, "to_pyarrow"):
                return result.to_pyarrow().to_pylist()
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return [result]
            return list(result)
        if isinstance(table, list):
            return table
        if isinstance(table, dict):
            return [table]
        return ibis.memtable(table).to_pyarrow().to_pylist()

    def _empty_results(self) -> list[dict[str, Any]]:
        return []

    def _validate_embedding_dimension(self, embeddings: list[list[float]]) -> None:
        if not embeddings:
            msg = "No embeddings provided"
            raise ValueError(msg)
        dimensions = {len(emb) for emb in embeddings}
        if len(dimensions) != 1:
            msg = f"Inconsistent embedding dimensions within batch: {sorted(dimensions)}"
            raise ValueError(msg)
        (dimension,) = dimensions
        if dimension != EMBEDDING_DIM:
            msg = (
                f"Embedding dimension mismatch. Expected {EMBEDDING_DIM}, "
                f"got {dimension}. All embeddings must use {EMBEDDING_DIM} dimensions."
            )
            raise ValueError(msg)

    def _get_stored_metadata(self) -> DatasetMetadata | None:
        if not self.parquet_path.exists():
            return None
        stats = self.parquet_path.stat()
        return DatasetMetadata(mtime_ns=stats.st_mtime_ns, size=stats.st_size, row_count=0)

    # Compatibility helpers used by caching layers
    def __len__(self) -> int:
        if self._table is None:
            return 0
        try:
            return len(self._table)
        except Exception:  # pragma: no cover - defensive
            return 0

    def table_exists(self) -> bool:
        return self._table is not None

    def get_indexed_sources_table(self) -> ibis.Table:
        """Return indexed sources as an Ibis table for delta detection."""

        schema = ibis.schema(
            {
                "source_path": dt.string,
                "source_mtime_ns": dt.int64,
            }
        )

        if self._table is None:
            return ibis.memtable([], schema=schema)

        arrow_table = self._table.to_arrow(columns=["source_path", "source_mtime_ns"])
        return ibis.memtable(arrow_table.to_pylist(), schema=schema)

    def get_indexed_sources(self) -> dict[str, int]:
        """Return mapping of source paths to mtime for incremental indexing."""

        if self._table is None:
            return {}

        arrow_table = self._table.to_arrow(columns=["source_path", "source_mtime_ns"])
        return {row["source_path"]: row["source_mtime_ns"] for row in arrow_table.to_pylist()}


def is_rag_available() -> bool:
    """RAG is available when LanceDB can be imported."""
    try:
        import lancedb as _  # noqa: F401
    except Exception:
        return False
    return True
