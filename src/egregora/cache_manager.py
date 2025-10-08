"""Thin wrapper around :mod:`diskcache` used by enrichment workflows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from diskcache import Cache


class CacheManager:
    """Persist enrichment payloads with minimal bookkeeping."""

    def __init__(self, cache_dir: Path, *, size_limit_mb: int | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        size_in_bytes = 0 if size_limit_mb is None else max(0, int(size_limit_mb)) * 1024 * 1024
        self._cache = Cache(directory=str(self.cache_dir), size_limit=size_in_bytes)
        self._cache_hits = 0
        self._cache_misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_uuid(self, url: str) -> str:
        """Return a stable UUID derived from the normalised URL."""

        normalised = self._normalise_url(url)
        return str(uuid.uuid5(uuid.NAMESPACE_URL, normalised))

    def exists(self, url: str) -> bool:
        """Return ``True`` if a payload is cached for *url*."""

        key = self.generate_uuid(url)
        entry = self._cache.get(key)
        return isinstance(entry, dict)

    def get(self, url: str) -> dict[str, Any] | None:
        """Fetch a cached payload or ``None`` when missing."""

        key = self.generate_uuid(url)
        entry = self._cache.get(key)
        if not isinstance(entry, dict):
            if entry is not None:
                self._cache.delete(key)
            self._cache_misses += 1
            return None

        now = datetime.now(UTC)
        entry["last_used"] = now
        entry["hit_count"] = int(entry.get("hit_count", 0)) + 1
        self._cache.set(key, entry)
        self._cache_hits += 1
        payload = entry.get("payload", {})
        return dict(payload)

    def set(self, url: str, analysis: dict[str, Any]) -> dict[str, Any]:
        """Persist *analysis* for *url* and return the stored payload."""

        key = self.generate_uuid(url)
        now = datetime.now(UTC)
        existing = self._cache.get(key)

        if isinstance(existing, dict):
            hit_count = int(existing.get("hit_count", 0))
            created_at = existing.get("first_seen", now)
        else:
            hit_count = 0
            created_at = now

        stored_payload = dict(analysis)
        stored_payload.setdefault("uuid", key)
        stored_payload.setdefault("url", url)
        stored_payload.setdefault("analyzed_at", now.isoformat())

        entry = {
            "payload": stored_payload,
            "first_seen": created_at,
            "last_used": now,
            "hit_count": hit_count,
        }

        self._cache.set(key, entry)
        return stored_payload

    def get_stats(self) -> dict[str, float | int | None]:
        """Expose cache hit/miss counters."""

        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests) if total_requests else 0.0
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": hit_rate,
            "total_entries": len(self._cache),
        }

    def cleanup_old_entries(self, days: int) -> int:
        """Remove entries whose ``last_used`` timestamp is older than ``days``."""

        threshold = datetime.now(UTC) - timedelta(days=days)
        removed = 0

        for key in list(self._cache.iterkeys()):
            entry = self._cache.get(key)
            if not isinstance(entry, dict):
                self._cache.delete(key)
                continue

            last_used = self._coerce_timestamp(entry.get("last_used"))
            if last_used is None:
                continue

            if last_used < threshold:
                self._cache.delete(key)
                removed += 1
                continue

            if not isinstance(entry.get("last_used"), datetime):
                entry["last_used"] = last_used
                self._cache.set(key, entry)

        return removed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_url(url: str) -> str:
        parts = urlparse(url)

        scheme = parts.scheme.lower()

        hostname = (parts.hostname or "").lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]

        if hostname and ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"

        default_port: int | None
        if scheme == "http":
            default_port = 80
        elif scheme == "https":
            default_port = 443
        else:
            default_port = None

        port = parts.port
        if default_port is not None and port == default_port:
            port = None

        userinfo = ""
        if parts.username:
            userinfo = parts.username
            if parts.password:
                userinfo += f":{parts.password}"
            userinfo += "@"

        netloc = hostname
        if port is not None and hostname:
            netloc = f"{hostname}:{port}"
        elif port is not None:
            netloc = f":{port}"

        netloc = f"{userinfo}{netloc}" if userinfo or netloc else userinfo

        path = parts.path
        if len(path) > 1:
            path = path.rstrip("/")

        query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)), doseq=True)

        return urlunparse((scheme, netloc, path, parts.params, query, ""))

    @staticmethod
    def _coerce_timestamp(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)

            return parsed.astimezone(UTC)

        return None


__all__ = ["CacheManager"]
