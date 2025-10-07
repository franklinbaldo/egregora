"""Disk-backed cache for URL enrichments built on :mod:`diskcache`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import hashlib
import uuid

from diskcache import Cache

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_STATS_KEY = "__egregora_cache_stats__"


@dataclass(slots=True)
class CacheStats:
    """Runtime statistics exposed to callers."""

    cache_hits: int = 0
    cache_misses: int = 0
    last_pruned_at: str | None = None

    def as_dict(self, total_entries: int) -> dict[str, float | int | None]:
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (
            self.cache_hits / total_requests if total_requests else 0.0
        )
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": hit_rate,
            "total_entries": total_entries,
            "last_pruned_at": self.last_pruned_at,
        }


class CacheManager:
    """Lightweight wrapper around :class:`diskcache.Cache` for enrichments."""

    def __init__(self, cache_dir: Path, *, size_limit_mb: int | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # diskcache uses 0 for no limit, not None.
        size_in_bytes = (
            0 if size_limit_mb is None else max(0, int(size_limit_mb)) * 1024 * 1024
        )
        self._cache = Cache(directory=str(self.cache_dir), size_limit=size_in_bytes)
        stats = self._cache.get(_STATS_KEY, default=None)
        self._stats = stats if isinstance(stats, CacheStats) else CacheStats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_uuid(self, url: str) -> str:
        """Generate a stable UUID from the normalised URL."""

        normalised = self._normalise_url(url)
        return str(uuid.uuid5(uuid.NAMESPACE_URL, normalised))

    def exists(self, url: str) -> bool:
        """Return ``True`` if *url* has a valid cached payload."""

        uuid_value = self.generate_uuid(url)
        entry = self._cache.get(uuid_value)
        return bool(entry and entry.get("url_hash") == self._hash_url(url))

    def get(self, url: str) -> dict[str, Any] | None:
        """Return cached payload for *url* or ``None`` when missing."""

        uuid_value = self.generate_uuid(url)
        entry = self._cache.get(uuid_value)
        if not entry or entry.get("url_hash") != self._hash_url(url):
            self._record_cache_miss()
            if entry:
                self._cache.delete(uuid_value)
            return None

        now_iso = self._now_iso()
        entry["last_used"] = now_iso
        entry["hit_count"] = int(entry.get("hit_count", 0)) + 1
        self._cache.set(uuid_value, entry)
        self._record_cache_hit()
        payload = entry.get("payload", {})
        return dict(payload)

    def set(self, url: str, analysis: dict[str, Any]) -> dict[str, Any]:
        """Store *analysis* for *url* returning the saved payload."""

        uuid_value = self.generate_uuid(url)
        now_iso = self._now_iso()
        existing = self._cache.get(uuid_value) or {}

        stored_payload = dict(analysis)
        stored_payload.setdefault("uuid", uuid_value)
        stored_payload.setdefault("url", url)
        stored_payload.setdefault("analyzed_at", now_iso)

        entry = {
            "payload": stored_payload,
            "url_hash": self._hash_url(url),
            "first_seen": existing.get("first_seen", now_iso),
            "last_used": now_iso,
            "hit_count": int(existing.get("hit_count", 0)),
        }

        self._cache.set(uuid_value, entry)
        self._persist_stats()
        return stored_payload

    def get_stats(self) -> dict[str, float | int | None]:
        """Return runtime statistics for the cache."""

        return self._stats.as_dict(self._total_entries())

    def cleanup_old_entries(self, days: int) -> int:
        """Remove entries older than ``days`` days. Returns deleted count."""

        threshold = self._now() - timedelta(days=days)
        removed = 0

        for key in list(self._cache.iterkeys()):
            if key == _STATS_KEY:
                continue
            entry = self._cache.get(key)
            if not entry:
                continue
            last_used = entry.get("last_used")
            last_dt = self._parse_iso(last_used) if last_used else None
            if last_dt and last_dt < threshold:
                self._cache.delete(key)
                removed += 1

        if removed:
            self._stats.last_pruned_at = self._now_iso()
            self._persist_stats()
        return removed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _record_cache_hit(self) -> None:
        self._stats.cache_hits += 1
        self._persist_stats()

    def _record_cache_miss(self) -> None:
        self._stats.cache_misses += 1
        self._persist_stats()

    def _persist_stats(self) -> None:
        self._cache.set(_STATS_KEY, self._stats)

    def _total_entries(self) -> int:
        keys = [key for key in self._cache.iterkeys() if key != _STATS_KEY]
        return len(keys)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _now_iso(cls) -> str:
        return cls._now().strftime(ISO_FORMAT)

    @staticmethod
    def _parse_iso(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, ISO_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _normalise_url(url: str) -> str:
        parsed = urlparse(url)
        query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))

        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        if parsed.port is not None:
            default_port = None
            if scheme == "http" and parsed.port == 80:
                default_port = 80
            elif scheme == "https" and parsed.port == 443:
                default_port = 443

            if default_port is not None:
                userinfo, at, host_port = netloc.rpartition("@")
                if host_port.endswith(f":{default_port}"):
                    host_port = host_port[: -len(f":{default_port}")]
                    netloc = f"{userinfo}{at}{host_port}" if at else host_port

        normalised = parsed._replace(
            scheme=scheme,
            netloc=netloc,
            query=query,
            fragment="",
        )
        return urlunparse(normalised)
        parts = urlparse(url)
        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        path = parts.path
        if len(path) > 1:
            path = path.rstrip('/')

        query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
        fragment = ""

        return urlunparse((scheme, netloc, path, parts.params, query, fragment))

    @classmethod
    def _hash_url(cls, url: str) -> str:
        return hashlib.sha256(cls._normalise_url(url).encode("utf-8")).hexdigest()


__all__ = ["CacheManager"]
