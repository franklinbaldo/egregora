"""Persistent cache for URL enrichments using diskcache."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

import diskcache

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class CacheManager:
    """Manage persisted analyses using diskcache to avoid reprocessing URLs."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Use diskcache.Cache for persistent storage
        self._cache = diskcache.Cache(str(self.cache_dir / "analyses"))

        # Stats tracking in separate cache
        self._stats_cache = diskcache.Cache(str(self.cache_dir / "stats"))
        self._init_stats()

    def _init_stats(self) -> None:
        """Initialize stats if not present."""
        if "cache_hits" not in self._stats_cache:
            self._stats_cache["cache_hits"] = 0
        if "cache_misses" not in self._stats_cache:
            self._stats_cache["cache_misses"] = 0
        if "last_cleanup" not in self._stats_cache:
            self._stats_cache["last_cleanup"] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_uuid(self, url: str) -> str:
        """Generate a deterministic cache key from a normalized URL."""
        normalized = self._normalize_url(url)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def exists(self, url: str) -> bool:
        """Return True if url is cached and valid."""
        key = self.generate_uuid(url)
        return key in self._cache

    def get(self, url: str) -> dict[str, Any] | None:
        """Return cached payload for url or None if not available."""
        key = self.generate_uuid(url)

        try:
            cached = self._cache.get(key)
            if cached is None or not isinstance(cached, dict):
                self._update_stats(hit=False)
                return None

            # Validate the cached entry has expected structure
            if "enrichment" not in cached or cached.get("status") != "valid":
                self._update_stats(hit=False)
                return None

            # Update hit count and last_used metadata
            cached.setdefault("hit_count", 0)
            cached["hit_count"] += 1
            cached["last_used"] = self._now()
            self._cache.set(key, cached)

            self._update_stats(hit=True)
            return cached
        except Exception:
            self._update_stats(hit=False)
            return None

    def set(self, url: str, analysis: dict[str, Any]) -> dict[str, Any]:
        """Persist analysis for url returning the stored payload."""
        key = self.generate_uuid(url)
        now = self._now()

        # Get existing entry to preserve first_seen and hit_count
        existing = self._cache.get(key)
        first_seen = existing.get("first_seen") if existing else now
        hit_count = existing.get("hit_count", 0) if existing else 0

        analysis_payload = {
            "uuid": key,
            "url": url,
            "url_hash": self._hash_url(url),
            "first_seen": first_seen,
            "last_used": now,
            "hit_count": hit_count,
            "analyzed_at": analysis.get("analyzed_at", now),
            "model": analysis.get("model"),
            "enrichment": analysis.get("enrichment", {}),
            "context": analysis.get("context", {}),
            "metadata": analysis.get("metadata", {}),
            "status": "valid",
        }

        self._cache.set(key, analysis_payload)
        return analysis_payload

    def get_stats(self) -> dict[str, Any]:
        """Return current statistics."""
        total_entries = len(self._cache)
        cache_hits = int(self._stats_cache.get("cache_hits", 0))
        cache_misses = int(self._stats_cache.get("cache_misses", 0))
        total = cache_hits + cache_misses

        return {
            "total_entries": total_entries,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": (cache_hits / total) if total else 0.0,
            "disk_usage_mb": self._calculate_disk_usage(),
            "last_cleanup": self._stats_cache.get("last_cleanup"),
            "top_domains": self._compute_top_domains(),
            "most_relevant_urls": self._compute_most_relevant(),
        }

    def cleanup_old_entries(self, days: int) -> int:
        """Delete analyses whose last_used is older than days."""
        threshold = datetime.now(timezone.utc) - timedelta(days=days)
        removed = 0

        # Iterate over all cached entries
        for key in list(self._cache.iterkeys()):
            try:
                entry = self._cache.get(key)
                if not entry or not isinstance(entry, dict):
                    continue

                last_used_str = entry.get("last_used")
                if not last_used_str:
                    continue

                last_used = self._parse_datetime(last_used_str)
                if last_used and last_used < threshold:
                    del self._cache[key]
                    removed += 1
            except Exception:
                continue

        self._stats_cache["last_cleanup"] = self._now()
        return removed

    def export_report(self) -> str:
        """Return a human-readable summary of cache usage."""
        stats = self.get_stats()

        lines = [
            "Egregora Cache Report",
            "====================",
            f"Entries stored: {stats['total_entries']}",
            f"Cache hits: {stats['cache_hits']}",
            f"Cache misses: {stats['cache_misses']}",
            f"Hit rate: {stats['cache_hit_rate']:.2%}",
            f"Disk usage (MB): {stats['disk_usage_mb']:.2f}",
        ]

        top_domains = stats.get("top_domains", {})
        if top_domains:
            lines.append("\nTop domains:")
            for domain, count in top_domains.items():
                lines.append(f"- {domain}: {count}")

        most_relevant = stats.get("most_relevant_urls", [])
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
    def _update_stats(self, *, hit: bool) -> None:
        """Update cache hit/miss statistics."""
        if hit:
            self._stats_cache.incr("cache_hits")
        else:
            self._stats_cache.incr("cache_misses")

    def _compute_top_domains(self) -> dict[str, int]:
        """Compute top 10 domains from cached URLs."""
        counter: Counter[str] = Counter()

        for key in self._cache.iterkeys():
            try:
                entry = self._cache.get(key)
                if not entry or not isinstance(entry, dict):
                    continue

                url = entry.get("url")
                if not url:
                    continue

                domain = urlparse(url).netloc.lower()
                if domain:
                    counter[domain] += 1
            except Exception:
                continue

        return dict(counter.most_common(10))

    def _compute_most_relevant(self) -> list[dict[str, Any]]:
        """Compute top 10 most relevant cached URLs."""
        ranked: list[tuple[int, int, str]] = []

        for key in self._cache.iterkeys():
            try:
                entry = self._cache.get(key)
                if not entry or not isinstance(entry, dict):
                    continue

                enrichment = entry.get("enrichment", {})
                relevance = enrichment.get("relevance")
                if not isinstance(relevance, int):
                    continue

                hit_count = int(entry.get("hit_count", 0))
                url = entry.get("url", "")
                ranked.append((relevance, hit_count, url))
            except Exception:
                continue

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)

        result: list[dict[str, Any]] = []
        for relevance, hit_count, url in ranked[:10]:
            result.append({
                "url": url,
                "relevance": relevance,
                "hit_count": hit_count,
            })
        return result

    def _calculate_disk_usage(self) -> float:
        """Calculate total disk usage in MB."""
        total_bytes = 0
        for path in self.cache_dir.rglob("*"):
            if path.is_file():
                try:
                    total_bytes += path.stat().st_size
                except OSError:
                    continue
        return round(total_bytes / (1024 * 1024), 3)

    def _hash_url(self, url: str) -> str:
        """Generate SHA256 hash of normalized URL."""
        normalized = self._normalize_url(url)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for consistent caching."""
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
        """Sort query parameters for consistent URLs."""
        if not query:
            return ""
        pairs = parse_qsl(query, keep_blank_values=True)
        pairs.sort()
        return urlencode(pairs)

    @staticmethod
    def _now() -> str:
        """Return current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).strftime(ISO_FORMAT)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse datetime from ISO format string."""
        if not value:
            return None
        try:
            return datetime.strptime(str(value), ISO_FORMAT).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
