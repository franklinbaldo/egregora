"""Persistent caching utilities for Gemini embeddings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable


@dataclass(slots=True)
class CachedEmbedding:
    """Container for cached embedding metadata."""

    dimension: int
    cached_at: datetime

    def to_dict(self) -> dict[str, str | int]:
        return {
            "dimension": self.dimension,
            "cached_at": self.cached_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "CachedEmbedding":
        cached_at = payload.get("cached_at")
        timestamp = datetime.fromisoformat(str(cached_at)) if cached_at else datetime.utcnow()
        return cls(dimension=int(payload.get("dimension", 0)), cached_at=timestamp)


class EmbeddingCache:
    """Simple file-based cache for embedding vectors."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.cache_dir / "index.json"
        self._index: dict[str, CachedEmbedding] = self._load_index()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, text: str) -> list[float] | None:
        """Return a cached embedding for *text* if available."""

        text_hash = self._hash_text(text)
        entry = self._index.get(text_hash)
        if not entry:
            return None

        payload_path = self.cache_dir / f"{text_hash}.json"
        if not payload_path.exists():
            return None

        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - defensive
            return None

        values = payload.get("embedding")
        if not isinstance(values, list):
            return None

        return [float(value) for value in values]

    def set(self, text: str, embedding: Iterable[float]) -> None:
        """Store *embedding* for *text* in the cache."""

        vector = [float(value) for value in embedding]
        text_hash = self._hash_text(text)
        payload_path = self.cache_dir / f"{text_hash}.json"

        payload = {"embedding": vector}
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        self._index[text_hash] = CachedEmbedding(
            dimension=len(vector),
            cached_at=datetime.utcnow(),
        )
        self._save_index()

    def clear(self) -> None:
        """Remove all cached embeddings."""

        for path in self.cache_dir.glob("*.json"):
            if path.name == "index.json":
                continue
            path.unlink(missing_ok=True)
        self._index.clear()
        self._save_index()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _hash_text(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return digest[:32]

    def _load_index(self) -> dict[str, CachedEmbedding]:
        if not self.index_path.exists():
            return {}

        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - defensive
            return {}

        entries = {}
        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            entries[key] = CachedEmbedding.from_dict(value)
        return entries

    def _save_index(self) -> None:
        payload = {key: entry.to_dict() for key, entry in self._index.items()}
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


__all__ = ["EmbeddingCache", "CachedEmbedding"]

