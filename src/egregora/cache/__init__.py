"""Disk-backed cache utilities for enrichment payloads."""

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
        hit_rate = self.cache_hits / total_requests if total_requests else 0.0
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": hit_rate,
            "total_entries": total_entries,
            "last_pruned_at": self.last_pruned_at,
        }


def create_enrichment_cache(
    cache_dir: Path, size_limit_mb: int | None = None
) -> Cache:
    """Return a configured :class:`diskcache.Cache` for enrichment payloads."""

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    size_limit = (
        None if size_limit_mb is None else max(0, int(size_limit_mb)) * 1024 * 1024
    )
    cache = Cache(directory=str(cache_path), size_limit=size_limit)
    _ensure_stats(cache)
    return cache


def cache_key_for_url(url: str) -> str:
    """Return a stable cache key for *url* using UUIDv5 and normalisation."""

    return str(uuid.uuid5(uuid.NAMESPACE_URL, _normalise_url(url)))


def has_enrichment(cache: Cache, url: str) -> bool:
    """Return ``True`` when a valid enrichment for ``url`` exists."""

    entry = cache.get(cache_key_for_url(url))
    return bool(entry and entry.get("url_hash") == _hash_url(url))


def load_enrichment(cache: Cache, url: str) -> dict[str, Any] | None:
    """Return cached enrichment for *url* or ``None`` when missing."""

    key = cache_key_for_url(url)
    entry = cache.get(key)
    if not entry or entry.get("url_hash") != _hash_url(url):
        _record_cache_miss(cache)
        if entry:
            cache.delete(key)
        return None

    entry["last_used"] = _now_iso()
    entry["hit_count"] = int(entry.get("hit_count", 0)) + 1
    cache.set(key, entry)
    _record_cache_hit(cache)

    payload = entry.get("payload")
    return dict(payload) if isinstance(payload, dict) else None


def store_enrichment(cache: Cache, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist *payload* for *url* returning the stored representation."""

    key = cache_key_for_url(url)
    now_iso = _now_iso()
    existing = cache.get(key) or {}

    stored_payload = dict(payload)
    stored_payload.setdefault("uuid", key)
    stored_payload.setdefault("url", url)
    stored_payload.setdefault("analyzed_at", now_iso)

    entry = {
        "payload": stored_payload,
        "url_hash": _hash_url(url),
        "first_seen": existing.get("first_seen", now_iso),
        "last_used": now_iso,
        "hit_count": int(existing.get("hit_count", 0)),
    }

    cache.set(key, entry)
    _ensure_stats(cache)
    return stored_payload


def get_enrichment_stats(cache: Cache) -> dict[str, float | int | None]:
    """Return statistics for enrichment cache usage."""

    stats = _ensure_stats(cache)
    return stats.as_dict(_total_entries(cache))


def cleanup_enrichment_cache(cache: Cache, days: int) -> int:
    """Remove entries older than ``days`` days. Returns deleted count."""

    threshold = _now() - timedelta(days=days)
    removed = 0

    for key in list(cache.iterkeys()):
        if key == _STATS_KEY:
            continue
        entry = cache.get(key)
        if not entry:
            continue
        last_used = entry.get("last_used")
        last_dt = _parse_iso(last_used) if last_used else None
        if last_dt and last_dt < threshold:
            cache.delete(key)
            removed += 1

    if removed:
        stats = _ensure_stats(cache)
        stats.last_pruned_at = _now_iso()
        _persist_stats(cache, stats)

    return removed


def _ensure_stats(cache: Cache) -> CacheStats:
    stats = cache.get(_STATS_KEY)
    if isinstance(stats, CacheStats):
        return stats

    stats = CacheStats()
    _persist_stats(cache, stats)
    return stats


def _record_cache_hit(cache: Cache) -> None:
    stats = _ensure_stats(cache)
    stats.cache_hits += 1
    _persist_stats(cache, stats)


def _record_cache_miss(cache: Cache) -> None:
    stats = _ensure_stats(cache)
    stats.cache_misses += 1
    _persist_stats(cache, stats)


def _persist_stats(cache: Cache, stats: CacheStats) -> None:
    cache.set(_STATS_KEY, stats)


def _total_entries(cache: Cache) -> int:
    keys = [key for key in cache.iterkeys() if key != _STATS_KEY]
    return len(keys)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().strftime(ISO_FORMAT)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, ISO_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _normalise_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    normalised = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=query,
        fragment="",
    )
    return urlunparse(normalised)


def _hash_url(url: str) -> str:
    return hashlib.sha256(_normalise_url(url).encode("utf-8")).hexdigest()


__all__ = [
    "CacheStats",
    "Cache",
    "ISO_FORMAT",
    "cache_key_for_url",
    "cleanup_enrichment_cache",
    "create_enrichment_cache",
    "get_enrichment_stats",
    "has_enrichment",
    "load_enrichment",
    "store_enrichment",
]
