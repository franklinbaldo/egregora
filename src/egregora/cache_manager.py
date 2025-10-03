"""Persistent JSON-based cache for URL enrichments."""

from __future__ import annotations

import json
import uuid
import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
INDEX_VERSION = "1.0"
STATS_VERSION = "1.0"


@dataclass(slots=True)
class CacheEntry:
    """Metadata describing a cached analysis stored on disk."""

    uuid: str
    url: str
    url_hash: str
    first_seen: str
    last_used: str
    hit_count: int
    analysis_path: str
    model_used: str | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "uuid": self.uuid,
            "url": self.url,
            "url_hash": self.url_hash,
            "first_seen": self.first_seen,
            "last_used": self.last_used,
            "hit_count": self.hit_count,
            "analysis_path": self.analysis_path,
            "model_used": self.model_used,
            "status": self.status,
        }


class CacheManager:
    """Manage persisted analyses to avoid reprocessing URLs."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.analyses_dir = self.cache_dir / "analyses"
        self.index_path = self.cache_dir / "index.json"
        self.stats_path = self.cache_dir / "stats.json"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.analyses_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, Any] = self._load_index()
        self._stats: dict[str, Any] = self._load_stats()
        self._save_stats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_uuid(self, url: str) -> str:
        """Generate a deterministic UUID (v5) from a normalized URL."""

        normalized = self._normalize_url(url)
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, normalized))

    def exists(self, url: str) -> bool:
        """Return ``True`` if *url* is cached and marked as valid."""

        entry = self._index["entries"].get(self.generate_uuid(url))
        return bool(entry and entry.get("status") == "valid")

    def get(self, url: str) -> Optional[dict[str, Any]]:
        """Return cached payload for *url* or ``None`` if not available."""

        uuid_value = self.generate_uuid(url)
        entry_dict = self._index["entries"].get(uuid_value)
        if not entry_dict or entry_dict.get("status") != "valid":
            self._update_stats(hit=False)
            return None

        if entry_dict.get("url_hash") != self._hash_url(url):
            entry_dict["status"] = "error"
            self._save_index()
            self._update_stats(hit=False)
            return None

        analysis_path = self._resolve_analysis_path(entry_dict.get("analysis_path"))
        if analysis_path is None or not analysis_path.exists():
            entry_dict["status"] = "error"
            self._save_index()
            self._update_stats(hit=False)
            return None

        try:
            cached = self._load_analysis(analysis_path)
        except (OSError, json.JSONDecodeError):
            entry_dict["status"] = "error"
            self._save_index()
            self._update_stats(hit=False)
            return None

        if cached.get("uuid") != uuid_value:
            entry_dict["status"] = "error"
            self._save_index()
            self._update_stats(hit=False)
            return None

        now = self._now()
        entry_dict["last_used"] = now
        entry_dict["hit_count"] = int(entry_dict.get("hit_count", 0)) + 1
        self._index["last_updated"] = now
        self._index["entries"][uuid_value] = entry_dict
        self._save_index()
        self._update_stats(hit=True)
        return cached

    def set(self, url: str, analysis: dict[str, Any]) -> dict[str, Any]:
        """Persist *analysis* for *url* returning the stored payload."""

        uuid_value = self.generate_uuid(url)
        now = self._now()
        existing = self._index["entries"].get(uuid_value)

        analysis_payload = {
            "uuid": uuid_value,
            "url": url,
            "analyzed_at": analysis.get("analyzed_at", now),
            "model": analysis.get("model"),
            "enrichment": analysis.get("enrichment", {}),
            "context": analysis.get("context", {}),
            "metadata": analysis.get("metadata", {}),
            "version": analysis.get("version", INDEX_VERSION),
        }

        analysis_path = self._get_analysis_path(uuid_value, now)
        if existing:
            existing_path = self._resolve_analysis_path(existing.get("analysis_path"))
            if (
                existing_path
                and existing_path != analysis_path
                and existing_path.exists()
            ):
                existing_path.unlink(missing_ok=True)
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_analysis(analysis_path, analysis_payload)

        relative_path = self._format_analysis_path(analysis_path)
        first_seen = existing.get("first_seen") if existing else now
        hit_count = existing.get("hit_count", 0) if existing else 0
        entry = CacheEntry(
            uuid=uuid_value,
            url=url,
            url_hash=self._hash_url(url),
            first_seen=first_seen,
            last_used=now,
            hit_count=hit_count,
            analysis_path=relative_path,
            model_used=analysis.get("model")
            or analysis.get("metadata", {}).get("model")
            or analysis_payload.get("model"),
            status="valid",
        )

        self._index["entries"][uuid_value] = entry.to_dict()
        self._index["total_entries"] = len(self._index["entries"])
        self._index["last_updated"] = now
        self._save_index()
        self._refresh_stats()
        return analysis_payload

    def get_stats(self) -> dict[str, Any]:
        """Return a shallow copy of the current statistics."""

        return dict(self._stats)

    def cleanup_old_entries(self, days: int) -> int:
        """Delete analyses whose ``last_used`` is older than *days* days."""

        threshold = self._now_datetime() - timedelta(days=days)
        removed = 0
        entries = dict(self._index["entries"])
        for uuid_value, data in entries.items():
            last_used = self._parse_datetime(data.get("last_used"))
            if last_used and last_used < threshold:
                analysis_path = self._resolve_analysis_path(data.get("analysis_path"))
                if analysis_path and analysis_path.exists():
                    analysis_path.unlink(missing_ok=True)
                self._index["entries"].pop(uuid_value, None)
                removed += 1

        if removed:
            now = self._now()
            self._index["last_updated"] = now
            self._index["total_entries"] = len(self._index["entries"])
            self._save_index()

        self._stats["last_cleanup"] = self._now()
        self._refresh_stats()
        return removed

    def export_report(self) -> str:
        """Return a human-readable summary of cache usage."""

        lines = [
            "Egregora Cache Report",
            "====================",
            f"Entries stored: {self._index.get('total_entries', 0)}",
            f"Cache hits: {self._stats.get('cache_hits', 0)}",
            f"Cache misses: {self._stats.get('cache_misses', 0)}",
            f"Hit rate: {self._stats.get('cache_hit_rate', 0):.2%}",
            f"Disk usage (MB): {self._stats.get('disk_usage_mb', 0.0):.2f}",
        ]

        top_domains = self._stats.get("top_domains", {})
        if top_domains:
            lines.append("\nTop domains:")
            for domain, count in top_domains.items():
                lines.append(f"- {domain}: {count}")

        most_relevant = self._stats.get("most_relevant_urls", [])
        if most_relevant:
            lines.append("\nMost relevant URLs:")
            for entry in most_relevant:
                url = entry.get("url")
                relevance = entry.get("relevance")
                hits = entry.get("hit_count")
                lines.append(f"- {url} (relevance {relevance}, hits {hits})")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_index(self) -> dict[str, Any]:
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        else:
            data = {}

        if not data:
            now = self._now()
            data = {
                "version": INDEX_VERSION,
                "last_updated": now,
                "total_entries": 0,
                "entries": {},
            }
        else:
            data.setdefault("version", INDEX_VERSION)
            data.setdefault("last_updated", self._now())
            data.setdefault("entries", {})
            data.setdefault("total_entries", len(data["entries"]))
        return data

    def _load_stats(self) -> dict[str, Any]:
        if self.stats_path.exists():
            try:
                data = json.loads(self.stats_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        else:
            data = {}

        if not data:
            return {
                "version": STATS_VERSION,
                "cache_hit_rate": 0.0,
                "total_analyses": self._index.get("total_entries", 0),
                "cache_hits": 0,
                "cache_misses": 0,
                "top_domains": {},
                "most_relevant_urls": [],
                "last_cleanup": None,
                "disk_usage_mb": 0.0,
            }

        data.setdefault("version", STATS_VERSION)
        data.setdefault("cache_hit_rate", 0.0)
        data.setdefault("total_analyses", self._index.get("total_entries", 0))
        data.setdefault("cache_hits", 0)
        data.setdefault("cache_misses", 0)
        data.setdefault("top_domains", {})
        data.setdefault("most_relevant_urls", [])
        data.setdefault("last_cleanup", None)
        data.setdefault("disk_usage_mb", 0.0)
        return data

    def _save_index(self) -> None:
        self.index_path.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _save_stats(self) -> None:
        self.stats_path.write_text(
            json.dumps(self._stats, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _get_analysis_path(self, uuid_value: str, timestamp: str) -> Path:
        dt = self._parse_datetime(timestamp) or self._now_datetime()
        folder = self.analyses_dir / f"{dt.year:04d}-{dt.month:02d}"
        filename = f"{uuid_value[:8]}-{uuid_value[9:13]}-{uuid_value[14:18]}.json"
        return folder / filename

    def _format_analysis_path(self, path: Path) -> str:
        try:
            relative = path.relative_to(self.cache_dir)
            return f"{self.cache_dir.name}/{relative.as_posix()}"
        except ValueError:
            return path.as_posix()

    def _resolve_analysis_path(self, stored_path: Any) -> Path | None:
        if not stored_path:
            return None
        raw_path = Path(str(stored_path))
        if raw_path.is_absolute():
            return raw_path
        if raw_path.parts and raw_path.parts[0] == self.cache_dir.name:
            relative = Path(*raw_path.parts[1:])
            return self.cache_dir / relative
        return self.cache_dir / raw_path

    def _load_analysis(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_analysis(self, path: Path, data: dict[str, Any]) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _update_stats(self, *, hit: bool) -> None:
        if hit:
            self._stats["cache_hits"] = int(self._stats.get("cache_hits", 0)) + 1
        else:
            self._stats["cache_misses"] = int(self._stats.get("cache_misses", 0)) + 1
        total = int(self._stats["cache_hits"]) + int(self._stats["cache_misses"])
        self._stats["cache_hit_rate"] = (self._stats["cache_hits"] / total) if total else 0.0
        self._stats["total_analyses"] = self._index.get("total_entries", 0)
        self._stats["disk_usage_mb"] = self._calculate_disk_usage()
        self._save_stats()

    def _refresh_stats(self) -> None:
        self._stats["total_analyses"] = self._index.get("total_entries", 0)
        self._stats["disk_usage_mb"] = self._calculate_disk_usage()
        self._stats["top_domains"] = self._compute_top_domains()
        self._stats["most_relevant_urls"] = self._compute_most_relevant()
        total = int(self._stats.get("cache_hits", 0)) + int(
            self._stats.get("cache_misses", 0)
        )
        self._stats["cache_hit_rate"] = (
            (self._stats.get("cache_hits", 0) or 0) / total if total else 0.0
        )
        self._save_stats()

    def _compute_top_domains(self) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for entry in self._index["entries"].values():
            url = entry.get("url")
            if not url:
                continue
            domain = urlparse(url).netloc.lower()
            if domain:
                counter[domain] += 1
        return dict(counter.most_common(10))

    def _compute_most_relevant(self) -> list[dict[str, Any]]:
        ranked: list[tuple[int, int, str]] = []
        for entry in self._index["entries"].values():
            analysis_path = self._resolve_analysis_path(entry.get("analysis_path"))
            if not analysis_path or not analysis_path.exists():
                continue
            try:
                data = self._load_analysis(analysis_path)
            except (OSError, json.JSONDecodeError):
                continue
            enrichment = data.get("enrichment", {})
            relevance = enrichment.get("relevance")
            if not isinstance(relevance, int):
                continue
            hit_count = int(entry.get("hit_count", 0))
            ranked.append((relevance, hit_count, data.get("url")))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        result: list[dict[str, Any]] = []
        for relevance, hit_count, url in ranked[:10]:
            result.append(
                {
                    "url": url,
                    "relevance": relevance,
                    "hit_count": hit_count,
                }
            )
        return result

    def _calculate_disk_usage(self) -> float:
        total_bytes = 0
        for path in self.cache_dir.rglob("*"):
            if path.is_file():
                try:
                    total_bytes += path.stat().st_size
                except OSError:
                    continue
        return round(total_bytes / (1024 * 1024), 3)

    def _hash_url(self, url: str) -> str:
        normalized = self._normalize_url(url)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        normalized_query = self._sort_query_params(parsed.query)
        normalized_path = parsed.path.rstrip("/") or "/"
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                normalized_path,
                parsed.params,
                normalized_query,
                "",
            )
        )

    @staticmethod
    def _sort_query_params(query: str) -> str:
        if not query:
            return ""
        pairs = parse_qsl(query, keep_blank_values=True)
        pairs.sort()
        return urlencode(pairs)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime(ISO_FORMAT)

    @staticmethod
    def _now_datetime() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(str(value), ISO_FORMAT).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

