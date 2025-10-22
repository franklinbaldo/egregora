"""ChromaDB-based RAG implementation."""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_URL, uuid5

import chromadb
import polars as pl

from ..models import GroupSource
from ..schema import ensure_message_schema
from ..transcript import load_source_dataframe
from .config import RAGConfig
from .embeddings import CachedGeminiEmbedding
from .indexer import list_markdown_files, split_into_chunks

if TYPE_CHECKING:
    from chromadb.api.types import QueryResult

logger = logging.getLogger(__name__)

_ROW_INDEX_COLUMN = "__row_index"


@dataclass(slots=True)
class _MessageEmbeddingBatch:
    ids: list[str]
    inputs: list[str]
    metadatas: list[dict[str, Any]]
    cache_entries: dict[tuple[str, str], pl.DataFrame]

    @property
    def is_empty(self) -> bool:
        return not self.ids


class _DailyFrameCache:
    """Simple bounded LRU cache for daily message frames."""

    def __init__(self, max_entries: int) -> None:
        self._max_entries = max(1, int(max_entries))
        self._store: OrderedDict[tuple[str, str], pl.DataFrame] = OrderedDict()

    def get(self, key: tuple[str, str]) -> pl.DataFrame | None:
        frame = self._store.get(key)
        if frame is None:
            return None
        self._store.move_to_end(key)
        return frame.clone()

    def set(self, key: tuple[str, str], frame: pl.DataFrame) -> None:
        self._store[key] = frame.clone()
        self._store.move_to_end(key)
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


class _MessageEmbeddingBuilder:
    """Prepare embedding inputs and metadata for message contexts."""

    def __init__(
        self,
        *,
        config: RAGConfig,
        group_slug: str,
        message_uuid,
        timestamp_formatter,
    ) -> None:
        self._config = config
        self._group_slug = group_slug
        self._message_uuid = message_uuid
        self._timestamp_formatter = timestamp_formatter
        self._radius_before = max(0, config.message_context_radius_before)
        self._radius_after = max(0, config.message_context_radius_after)

    def build(self, frame: pl.DataFrame) -> _MessageEmbeddingBatch:
        if frame.is_empty():
            return _MessageEmbeddingBatch([], [], [], {})

        sorted_frame = frame.sort("timestamp")
        partitions = sorted_frame.partition_by("date", maintain_order=True)
        if not partitions:
            partitions = [sorted_frame]

        prepared_partitions: list[pl.DataFrame] = []
        cache_entries: dict[tuple[str, str], pl.DataFrame] = {}

        for partition in partitions:
            base = partition.sort("timestamp").with_row_index(_ROW_INDEX_COLUMN)
            if base.is_empty():
                continue

            iso_date = str(base.get_column("date")[0])
            cache_entries[(self._group_slug, iso_date)] = base

            annotated = self._annotate_context_windows(base)
            prepared = self._prepare_segments(annotated).with_columns(
                pl.lit(iso_date).alias("date"),
            )

            if not prepared.is_empty():
                prepared_partitions.append(prepared)

        if not prepared_partitions:
            return _MessageEmbeddingBatch([], [], [], cache_entries)

        combined = pl.concat(prepared_partitions, how="vertical")

        ids = (
            combined
            .select(
                pl.struct(
                    pl.lit(self._group_slug).alias("group_slug"),
                    pl.col("timestamp"),
                    pl.col("author"),
                    pl.col("message"),
                ).map_elements(
                    lambda row: self._message_uuid(
                        group_slug=row["group_slug"],
                        timestamp=row["timestamp"],
                        author=row["author"] or "",
                        message=row["message"] or "",
                    ),
                    return_dtype=pl.Utf8,
                )
            )
            .to_series()
            .to_list()
        )

        inputs = combined.get_column("segment_text").to_list()

        metadata = (
            combined
            .select(
                pl.lit("message").alias("kind"),
                pl.lit(self._group_slug).alias("group_slug"),
                pl.col("timestamp")
                .map_elements(self._timestamp_formatter, return_dtype=pl.Utf8)
                .alias("timestamp"),
                pl.col(_ROW_INDEX_COLUMN).alias("message_index"),
                pl.col("context_start"),
                pl.col("context_end"),
                pl.col("date"),
            )
            .to_dicts()
        )

        return _MessageEmbeddingBatch(ids, inputs, metadata, cache_entries)

    def _annotate_context_windows(self, frame: pl.DataFrame) -> pl.DataFrame:
        if frame.is_empty():
            return frame

        max_index = frame.height - 1
        row_index = pl.col(_ROW_INDEX_COLUMN).cast(pl.Int64)
        annotated = frame.with_columns(
            row_index
            .sub(self._radius_before)
            .clip(lower_bound=0)
            .alias("context_start"),
            row_index
            .add(self._radius_after)
            .clip(upper_bound=max_index)
            .alias("context_end"),
        )

        return annotated.with_columns(
            pl.int_ranges(
                pl.col("context_start"),
                pl.col("context_end") + 1,
            ).alias("context_indices")
        )

    def _prepare_segments(self, frame: pl.DataFrame) -> pl.DataFrame:
        if frame.is_empty():
            return frame

        context_lookup = frame.select(
            pl.col(_ROW_INDEX_COLUMN).cast(pl.Int64).alias("context_index"),
            pl.col("timestamp").alias("context_timestamp"),
            pl.col("author").alias("context_author"),
            pl.col("message").alias("context_message"),
        ).with_columns(
            pl.col("context_timestamp")
            .map_elements(ChromadbRAG._format_time, return_dtype=pl.Utf8)
            .alias("context_time_display"),
            pl.when(
                pl.col("context_author").is_null()
                | (pl.col("context_author") == "")
            )
            .then(pl.lit("(autor desconhecido)"))
            .otherwise(pl.col("context_author"))
            .alias("context_author_display"),
            pl.col("context_message").fill_null("").alias("context_message_display"),
        )

        window = (
            frame
            .with_columns(pl.col("context_indices"))
            .explode("context_indices")
            .rename({"context_indices": "context_index"})
            .with_columns(pl.col("context_index").cast(pl.Int64))
            .join(context_lookup, on="context_index", how="left")
            .with_columns(
                (pl.col("context_index") == pl.col(_ROW_INDEX_COLUMN)).alias("context_highlight"),
            )
            .with_columns(
                self._render_segment().alias("context_line"),
            )
            .sort([_ROW_INDEX_COLUMN, "context_index"])
        )

        aggregated = window.group_by(_ROW_INDEX_COLUMN).agg(
            pl.col("context_index").min().alias("context_start"),
            pl.col("context_index").max().alias("context_end"),
            pl.col("context_line").implode().alias("_context_lines"),
        )

        return (
            aggregated.join(frame, on=_ROW_INDEX_COLUMN, how="left")
            .with_columns(
                pl.col("_context_lines")
                .map_elements(
                    lambda values: "\n".join(
                        item
                        for value in values
                        for item in (
                            value.to_list()
                            if isinstance(value, pl.Series)
                            else (value if isinstance(value, list) else [value])
                        )
                    ),
                    return_dtype=pl.Utf8,
                )
                .fill_null("<target_message></target_message>")
                .alias("segment_text"),
            )
            .drop("_context_lines", "context_indices")
        )

    @staticmethod
    def _render_segment() -> pl.Expr:
        base_line = pl.format(
            "{} — {}: {}",
            pl.col("context_time_display"),
            pl.col("context_author_display"),
            pl.col("context_message_display"),
        )
        return pl.when(pl.col("context_highlight")).then(
            pl.format("<target_message>{}</target_message>", base_line)
        ).otherwise(base_line)


class _SearchHydrator:
    """Augment search results with rehydrated message contexts."""

    def __init__(self, rag: ChromadbRAG) -> None:
        self._rag = rag

    def enrich(self, results: QueryResult) -> QueryResult:
        metadatas = results.get("metadatas")
        if not metadatas:
            return results

        entries = metadatas[0]
        documents = results.get("documents")
        docs = list(documents[0]) if documents and documents[0] else [""] * len(entries)
        if len(docs) < len(entries):
            docs.extend([""] * (len(entries) - len(docs)))

        for index, metadata in enumerate(entries):
            if not isinstance(metadata, dict):
                continue
            if docs[index]:
                continue
            rehydrated = self._rehydrate_document(metadata)
            if rehydrated is not None:
                docs[index] = rehydrated

        results["documents"] = [docs]
        return results

    def _rehydrate_document(self, metadata: dict[str, Any]) -> str | None:
        if metadata.get("kind") != "message":
            return None

        group_slug = metadata.get("group_slug")
        iso_date = metadata.get("date")
        if not group_slug or not iso_date:
            return None

        frame = self._rag._get_daily_frame(group_slug, iso_date)
        if frame is None or frame.is_empty():
            return None

        start = int(metadata.get("context_start", metadata.get("message_index", 0)))
        end = int(metadata.get("context_end", start))
        subset = frame.filter(
            (pl.col(_ROW_INDEX_COLUMN) >= start) & (pl.col(_ROW_INDEX_COLUMN) <= end)
        )
        if subset.is_empty():
            return None

        target_index = int(metadata.get("message_index", start))
        lines: list[str] = []
        for row in subset.iter_rows(named=True):
            row_index = int(row.get(_ROW_INDEX_COLUMN, -1))
            lines.append(
                self._rag._format_context_line(
                    row,
                    highlight=row_index == target_index,
                )
            )
        return "\n".join(lines)


class ChromadbRAG:
    """Handles RAG operations for posts using ChromaDB directly."""

    def __init__(self, config: RAGConfig, *, source: GroupSource | None = None, batch_client: object | None = None):
        self.config = config
        self.source = source
        self.embed_model = CachedGeminiEmbedding(
            model_name=self.config.embedding_model,
            dimension=self.config.embedding_dimension,
            cache_dir=self.config.cache_dir,
            use_batch_api=True,  # Enable batch API by default
            batch_threshold=20,  # Use batch API for 20+ embeddings
            batch_client=batch_client,
        )
        self.client = chromadb.PersistentClient(path=str(self.config.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=self.config.collection_name,
        )
        self._daily_frames = _DailyFrameCache(max_entries=self.config.max_cached_days)
        self._source_frame: pl.DataFrame | None = None
        self._hydrator = _SearchHydrator(self)

    # ------------------------------------------------------------------
    # Indexing helpers
    # ------------------------------------------------------------------

    def index_files(self, files_dir: Path, *, group_slug: str | None = None) -> None:
        """Index all markdown files in a directory."""
        files = list_markdown_files(files_dir)
        if not files:
            logger.info("No markdown files found to index in %s", files_dir)
            return

        logger.info("Indexing %d markdown files from %s", len(files), files_dir)
        for file_path in files:
            self.index_file(file_path, group_slug=group_slug)

    def index_file(self, file_path: Path, *, group_slug: str | None = None) -> None:
        """Index a single markdown file."""
        logger.info("Indexing %s", file_path)
        text = file_path.read_text(encoding="utf-8")
        chunks = self._chunk_markdown(text)

        if not chunks:
            return

        documents = [chunk[1] for chunk in chunks]
        embeddings = self.embed_model(documents)
        metadatas = [
            {
                "kind": "post_chunk",
                "source": str(file_path),
                "title": chunk[0] or "",
                "group_slug": group_slug,
            }
            for chunk in chunks
        ]
        ids = [f"{file_path}:{i}" for i in range(len(chunks))]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def upsert_messages(self, df: pl.DataFrame, *, group_slug: str) -> None:
        """Index chat messages without storing raw text in ChromaDB."""

        frame = ensure_message_schema(df)
        if frame.is_empty():
            return

        builder = _MessageEmbeddingBuilder(
            config=self.config,
            group_slug=group_slug,
            message_uuid=self._message_uuid,
            timestamp_formatter=self._timestamp_to_iso,
        )
        batch = builder.build(frame)
        if batch.is_empty:
            return

        embeddings = self.embed_model(batch.inputs)
        self.collection.upsert(
            ids=batch.ids,
            embeddings=embeddings,
            metadatas=batch.metadatas,
        )

        for key, cached in batch.cache_entries.items():
            self._daily_frames.set(key, cached)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def search(self, query: str, *, group_slug: str | None = None) -> QueryResult:
        """Search the vector store and rehydrate message contexts when needed."""
        query_embedding = self.embed_model([query])[0]
        slug = group_slug or (self.source.slug if self.source else None)

        where = {"group_slug": slug} if slug else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=self.config.top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        return self._hydrator.enrich(results)

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _chunk_markdown(self, text: str) -> list[tuple[str | None, str]]:
        return split_into_chunks(
            text,
            chunk_chars=self.config.chunk_size,
            overlap_chars=self.config.chunk_overlap,
        )

    @staticmethod
    def _timestamp_to_iso(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _format_time(value: Any) -> str:
        if value is None:
            return ""
        try:
            if hasattr(value, "strftime"):
                return value.strftime("%H:%M")
        except (TypeError, ValueError):  # pragma: no cover - defensive fallback
            pass
        return str(value)

    @staticmethod
    def _format_context_line(row: dict[str, Any], *, highlight: bool = False) -> str:
        timestamp = row.get("timestamp")
        author = row.get("author") or "(autor desconhecido)"
        message = row.get("message") or ""
        time_str = ChromadbRAG._format_time(timestamp)
        line = f"{time_str} — {author}: {message}"
        if highlight:
            return f"<target_message>{line}</target_message>"
        return line

    @staticmethod
    def _message_uuid(*, group_slug: str, timestamp: Any, author: str, message: str) -> str:
        base = "|".join(
            [
                group_slug or "",
                ChromadbRAG._timestamp_to_iso(timestamp),
                author or "",
                message or "",
            ]
        )
        return str(uuid5(NAMESPACE_URL, base))

    def _get_daily_frame(self, group_slug: str, iso_date: str) -> pl.DataFrame | None:
        key = (group_slug, iso_date)
        cached = self._daily_frames.get(key)
        if cached is not None:
            return cached

        if self.source is None or self.source.slug != group_slug:
            return None

        if self._source_frame is None:
            self._source_frame = load_source_dataframe(self.source)
        if self._source_frame is None or self._source_frame.is_empty():
            return None

        try:
            target_date = date.fromisoformat(iso_date)
        except ValueError:
            return None

        frame = (
            self._source_frame.filter(pl.col("date") == target_date)
            .sort("timestamp")
            .with_row_count(_ROW_INDEX_COLUMN)
        )
        self._daily_frames.set(key, frame)
        return self._daily_frames.get(key)

    def export_embeddings_to_parquet(self, output_path: Path) -> None:
        """Export all embeddings from ChromaDB to a parquet file."""
        import polars as pl
        from pathlib import Path
        
        try:
            # Get all documents and embeddings from ChromaDB
            collection = self.collection
            results = collection.get(include=["documents", "embeddings", "metadatas"])
            
            if not results["documents"]:
                print("No embeddings found in ChromaDB")
                return
                
            # Create a polars dataframe with embeddings and metadata
            data = {
                "id": results["ids"],
                "document": results["documents"],
                "embedding": results["embeddings"],
                "metadata": results["metadatas"]
            }
            
            # Convert to polars DataFrame
            df = pl.DataFrame(data)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Export to parquet
            df.write_parquet(output_path)
            print(f"✅ Exported {len(results['documents'])} embeddings to {output_path}")
            
        except Exception as e:
            print(f"❌ Failed to export embeddings: {e}")


__all__ = ["ChromadbRAG"]
