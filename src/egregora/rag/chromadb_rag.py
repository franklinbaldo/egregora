"""ChromaDB-based RAG implementation."""

from __future__ import annotations

import logging
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

#TODO: This class has a lot of logic for indexing and searching. It could be split into smaller classes.
class ChromadbRAG:
    """Handles RAG operations for posts using ChromaDB directly."""

    def __init__(self, config: RAGConfig, *, source: GroupSource | None = None):
        self.config = config
        self.source = source
        self.embed_model = CachedGeminiEmbedding(
            model_name=self.config.embedding_model,
            dimension=self.config.embedding_dimension,
            cache_dir=self.config.cache_dir,
        )
        self.client = chromadb.PersistentClient(path=str(self.config.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=self.config.collection_name,
        )
        self._daily_frame_cache: dict[tuple[str, str], pl.DataFrame] = {}
        self._source_frame: pl.DataFrame | None = None

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

    #TODO: The chunking logic is in a separate function. It would be better to have the chunking logic in this class.
    def index_file(self, file_path: Path, *, group_slug: str | None = None) -> None:
        """Index a single markdown file."""
        logger.info("Indexing %s", file_path)
        text = file_path.read_text(encoding="utf-8")
        chunks = split_into_chunks(
            text,
            chunk_chars=self.config.chunk_size,
            overlap_chars=self.config.chunk_overlap,
        )

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

    #TODO: The logic for creating the embedding text is a bit complex.
    def upsert_messages(self, df: pl.DataFrame, *, group_slug: str) -> None:
        """Index chat messages without storing raw text in ChromaDB."""

        frame = ensure_message_schema(df)
        if frame.is_empty():
            return

        frame = frame.sort("timestamp")
        partitions = frame.partition_by("date", maintain_order=True)
        if not partitions:
            partitions = [frame]

        radius_before = max(0, self.config.message_context_radius_before)
        radius_after = max(0, self.config.message_context_radius_after)
        ids: list[str] = []
        inputs: list[str] = []
        metadatas: list[dict[str, Any]] = []
        cached_frames: dict[str, pl.DataFrame] = {}

        for day_frame in partitions:
            if day_frame.is_empty():
                continue
            annotated_frame = day_frame.sort("timestamp").with_row_count(_ROW_INDEX_COLUMN)
            date_value = annotated_frame.get_column("date")[0]
            iso_date = str(date_value)
            cached_frames[iso_date] = annotated_frame
            height = annotated_frame.height

            for row in annotated_frame.iter_rows(named=True):
                index = int(row[_ROW_INDEX_COLUMN])
                message_text = row.get("message") or ""
                timestamp = row.get("timestamp")
                author = row.get("author") or ""

                message_id = self._message_uuid(
                    group_slug=group_slug,
                    timestamp=timestamp,
                    author=author,
                    message=message_text,
                )

                context_start = max(0, index - radius_before)
                context_end = min(height - 1, index + radius_after)
                segment_length = context_end - context_start + 1
                segment = annotated_frame.slice(context_start, segment_length)

                context_lines: list[str] = []
                for ctx_row in segment.iter_rows(named=True):
                    row_index = int(ctx_row.get(_ROW_INDEX_COLUMN, -1))
                    context_lines.append(
                        self._format_context_line(
                            ctx_row,
                            highlight=row_index == index,
                        )
                    )

                embedding_text = "\n".join(context_lines).strip()
                if not embedding_text:
                    embedding_text = "<target_message></target_message>"

                ids.append(message_id)
                inputs.append(embedding_text)
                metadatas.append(
                    {
                        "kind": "message",
                        "group_slug": group_slug,
                        "date": iso_date,
                        "timestamp": self._timestamp_to_iso(timestamp),
                        "message_index": index,
                        "context_start": context_start,
                        "context_end": context_end,
                    }
                )

        if not ids:
            return

        embeddings = self.embed_model(inputs)
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        for iso_date, cached in cached_frames.items():
            self._daily_frame_cache[(group_slug, iso_date)] = cached

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    #TODO: The logic for rehydrating the documents is a bit complex.
    def search(self, query: str, *, group_slug: str | None = None) -> QueryResult:
        """Search the vector store and rehydrate message contexts when needed."""

        query_embedding = self.embed_model([query])[0]
        slug = group_slug or (self.source.slug if self.source else None)

        where = {"group_slug": slug} if slug else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=self.config.top_k,
            where=where,
            include=["documents", "metadatas", "ids", "distances"],
        )

        metadatas = results.get("metadatas")
        if not metadatas:
            return results

        meta_entries = metadatas[0]
        documents = results.get("documents")
        if documents and documents[0]:
            docs = list(documents[0])
        else:
            docs = [""] * len(meta_entries)

        if len(docs) < len(meta_entries):
            docs.extend([""] * (len(meta_entries) - len(docs)))

        for idx, metadata in enumerate(meta_entries):
            if not isinstance(metadata, dict):
                continue
            if docs[idx]:
                continue

            rehydrated = self._rehydrate_document(metadata)
            if rehydrated is not None:
                docs[idx] = rehydrated

        results["documents"] = [docs]
        return results

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

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
        except Exception:  # pragma: no cover - defensive fallback
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

    def _rehydrate_document(self, metadata: dict[str, Any]) -> str | None:
        if metadata.get("kind") != "message":
            return None

        group_slug = metadata.get("group_slug")
        iso_date = metadata.get("date")
        if not group_slug or not iso_date:
            return None

        frame = self._get_daily_frame(group_slug, iso_date)
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
                self._format_context_line(
                    row,
                    highlight=row_index == target_index,
                )
            )
        return "\n".join(lines)

    #FIXME: The cache is a dictionary, and it might grow indefinitely.
    def _get_daily_frame(self, group_slug: str, iso_date: str) -> pl.DataFrame | None:
        key = (group_slug, iso_date)
        cached = self._daily_frame_cache.get(key)
        if cached is not None:
            return cached

        if self.source is None or self.source.slug != group_slug:
            return None

        if self._source_frame is None:
            self._source_frame = load_source_dataframe(self.source)

        try:
            target_date = date.fromisoformat(iso_date)
        except ValueError:
            return None

        frame = (
            self._source_frame.filter(pl.col("date") == target_date)
            .sort("timestamp")
            .with_row_count(_ROW_INDEX_COLUMN)
        )
        self._daily_frame_cache[key] = frame
        return frame


__all__ = ["ChromadbRAG"]