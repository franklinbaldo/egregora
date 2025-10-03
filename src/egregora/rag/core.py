"""Core data structures and operations for the newsletter RAG index."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Mapping

from ..config import RAGConfig
from . import indexer
from .search import (
    build_query_vector,
    build_vector,
    inverse_document_frequency,
    term_frequency,
    tokenize,
    cosine_similarity,
)

INDEX_VERSION = 1


@dataclass(slots=True)
class NewsletterChunk:
    """Represents a chunk of a newsletter."""

    chunk_id: str
    newsletter_path: Path
    newsletter_date: date
    section_title: str | None
    text: str

    def to_dict(self) -> Dict[str, str | None]:
        return {
            "id": self.chunk_id,
            "path": str(self.newsletter_path),
            "date": self.newsletter_date.isoformat(),
            "section": self.section_title,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "NewsletterChunk":
        return cls(
            chunk_id=str(payload["id"]),
            newsletter_path=Path(str(payload["path"])),
            newsletter_date=date.fromisoformat(str(payload["date"])),
            section_title=str(payload["section"]) if payload.get("section") else None,
            text=str(payload["text"]),
        )


@dataclass(slots=True)
class SearchHit:
    """A matching chunk with its similarity score."""

    chunk: NewsletterChunk
    score: float


@dataclass(slots=True)
class IndexStats:
    """Statistics about the current index."""

    total_newsletters: int
    total_chunks: int
    last_updated: datetime | None
    index_path: Path


@dataclass(slots=True)
class IndexUpdateResult:
    """Outcome from :meth:`NewsletterRAG.update_index`."""

    new_count: int
    modified_count: int
    deleted_count: int
    total_chunks: int


class NewsletterRAG:
    """Manage a lightweight semantic index of newsletter archives."""

    def __init__(
        self,
        *,
        newsletters_dir: Path,
        cache_dir: Path,
        config: RAGConfig | None = None,
    ) -> None:
        self.newsletters_dir = newsletters_dir.expanduser()
        self.cache_dir = cache_dir.expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.cache_dir / "rag_index.json"
        self.config = copy.deepcopy(config) if config else RAGConfig()

        self._chunks: list[NewsletterChunk] = []
        self._vectors: list[Dict[str, float]] = []
        self._idf: Dict[str, float] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------
    def load_index(self) -> None:
        """Load the index from disk, building it if necessary."""

        if self._loaded:
            return

        if not self.index_path.exists():
            self.update_index(force_reindex=True)
        else:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            newsletters = data.get("newsletters", {})
            for info in newsletters.values():
                for chunk_payload in info.get("chunks", []):
                    chunk = NewsletterChunk.from_dict(chunk_payload)
                    self._chunks.append(chunk)

        self._rebuild_vectors()
        self._loaded = True

    def _rebuild_vectors(self) -> None:
        tokens_per_chunk = [term_frequency(tokenize(chunk.text)) for chunk in self._chunks]
        self._idf = inverse_document_frequency(tokens_per_chunk)
        self._vectors = [build_vector(tf, self._idf) for tf in tokens_per_chunk]

    def update_index(self, *, force_reindex: bool = False) -> IndexUpdateResult:
        """Rebuild the index from the newsletters directory."""

        existing = {}
        metadata = {}

        if not force_reindex and self.index_path.exists():
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            existing = data.get("newsletters", {})
            metadata = data.get("metadata", {})

        newsletters = {}
        new_count = modified_count = 0
        total_chunks = 0

        for newsletter_path in indexer.list_markdown_files(self.newsletters_dir):
            text = newsletter_path.read_text(encoding="utf-8")
            content_hash = indexer.hash_text(text)

            previous = existing.get(str(newsletter_path))
            if not force_reindex and previous and previous.get("hash") == content_hash:
                newsletters[str(newsletter_path)] = previous
                total_chunks += len(previous.get("chunks", []))
                continue

            newsletter_date = indexer.detect_newsletter_date(newsletter_path) or date.today()
            chunks: list[dict[str, object]] = []
            for idx, (section, chunk_text) in enumerate(
                indexer.split_into_chunks(
                    text,
                    chunk_chars=self.config.max_context_chars,
                    overlap_chars=max(0, self.config.max_context_chars // 5),
                ),
                start=1,
            ):
                chunk_id = f"{newsletter_path.stem}-{idx}"
                chunks.append(
                    {
                        "id": chunk_id,
                        "section": section,
                        "text": chunk_text,
                        "date": newsletter_date.isoformat(),
                        "path": str(newsletter_path),
                    }
                )

            newsletters[str(newsletter_path)] = {
                "hash": content_hash,
                "chunks": chunks,
            }

            if previous:
                modified_count += 1
            else:
                new_count += 1

            total_chunks += len(chunks)

        deleted_count = sum(1 for key in existing.keys() if key not in newsletters)

        payload = {
            "version": INDEX_VERSION,
            "updated_at": datetime.utcnow().isoformat(),
            "newsletters": newsletters,
            "metadata": metadata,
        }
        self.index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        self._chunks = [
            NewsletterChunk.from_dict(chunk_payload)
            for item in newsletters.values()
            for chunk_payload in item.get("chunks", [])
        ]
        self._rebuild_vectors()
        self._loaded = True

        return IndexUpdateResult(
            new_count=new_count,
            modified_count=modified_count,
            deleted_count=deleted_count,
            total_chunks=total_chunks,
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def search(
        self,
        *,
        query: str,
        top_k: int | None = None,
        min_similarity: float | None = None,
        exclude_recent_days: int | None = None,
    ) -> list[SearchHit]:
        """Return semantic matches for the provided ``query``."""

        if not query.strip():
            return []

        if not self._loaded:
            self.load_index()

        if not self._chunks:
            return []

        vector = build_query_vector(query, self._idf)
        if not vector:
            return []

        limit = top_k or self.config.top_k
        threshold = min_similarity if min_similarity is not None else self.config.min_similarity
        exclude_days = (
            exclude_recent_days if exclude_recent_days is not None else self.config.exclude_recent_days
        )

        cutoff_date: date | None = None
        if exclude_days and exclude_days > 0:
            cutoff_date = date.today() - timedelta(days=exclude_days)

        hits: list[SearchHit] = []
        for chunk, chunk_vector in zip(self._chunks, self._vectors):
            if cutoff_date and chunk.newsletter_date >= cutoff_date:
                continue
            score = cosine_similarity(vector, chunk_vector)
            if score < threshold:
                continue
            hits.append(SearchHit(chunk=chunk, score=score))

        hits.sort(key=lambda item: item.score, reverse=True)
        if limit:
            hits = hits[:limit]
        return hits

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def get_stats(self) -> IndexStats:
        """Return high level information about the current index."""

        if not self._loaded:
            self.load_index()

        last_updated = None
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
                timestamp = data.get("updated_at")
                if isinstance(timestamp, str):
                    last_updated = datetime.fromisoformat(timestamp)
            except Exception:  # pragma: no cover - defensive
                last_updated = None

        newsletters = {chunk.newsletter_path for chunk in self._chunks}

        return IndexStats(
            total_newsletters=len(newsletters),
            total_chunks=len(self._chunks),
            last_updated=last_updated,
            index_path=self.index_path,
        )
