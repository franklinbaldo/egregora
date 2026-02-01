"""Connection Health Report generation.

Implements RFC 041: Connection Health Report (The Ghost Report).
Queries the staging_messages table to calculate relationship metrics
per author: first/last seen, message count, and silence duration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AuthorHealth", "get_connection_health_data"]

# Silence thresholds in days for connection status classification
_HOT_THRESHOLD = 7
_WARM_THRESHOLD = 30
_COOL_THRESHOLD = 90
_COLD_THRESHOLD = 180
_FROZEN_THRESHOLD = 365
# Above _FROZEN_THRESHOLD = "Ghost"

# Minimum messages to be included in the report (filter one-offs)
_MIN_MESSAGES = 5


@dataclass(frozen=True, slots=True)
class AuthorHealth:
    """Health metrics for a single author connection."""

    author_uuid: str
    author_name: str
    first_seen: datetime
    last_seen: datetime
    msg_count: int
    days_since_last: int
    status: str

    @property
    def years_active(self) -> float:
        """Duration between first and last message in years."""
        delta = self.last_seen - self.first_seen
        return round(delta.days / 365.25, 1)

    @property
    def messages_per_year(self) -> float:
        """Average messages per year over the active period."""
        years = self.years_active
        if years <= 0:
            return float(self.msg_count)
        return round(self.msg_count / years, 1)


def _classify_status(days_since_last: int) -> str:
    """Classify connection status based on silence duration."""
    if days_since_last <= _HOT_THRESHOLD:
        return "Hot"
    if days_since_last <= _WARM_THRESHOLD:
        return "Warm"
    if days_since_last <= _COOL_THRESHOLD:
        return "Cool"
    if days_since_last <= _COLD_THRESHOLD:
        return "Cold"
    if days_since_last <= _FROZEN_THRESHOLD:
        return "Frozen"
    return "Ghost"


def get_connection_health_data(
    pipeline_db_path: Path,
    profiles_dir: Path | None = None,
    *,
    min_messages: int = _MIN_MESSAGES,
    now: datetime | None = None,
) -> list[AuthorHealth]:
    """Query staging_messages to build connection health metrics.

    Args:
        pipeline_db_path: Path to the pipeline DuckDB database file.
        profiles_dir: Optional path to profiles directory for resolving author names.
        min_messages: Minimum message count to include an author (filters one-offs).
        now: Override for current time (useful for testing).

    Returns:
        List of AuthorHealth entries sorted by days_since_last descending (ghosts first).

    """
    if not pipeline_db_path or not pipeline_db_path.exists():
        logger.debug("Pipeline database not found at %s, skipping health report", pipeline_db_path)
        return []

    now = now or datetime.now(UTC)

    try:
        from egregora.database.duckdb_manager import DuckDBStorageManager

        with DuckDBStorageManager(pipeline_db_path) as storage:
            if not storage.table_exists("staging_messages"):
                logger.debug("staging_messages table not found, skipping health report")
                return []

            table = storage.read_table("staging_messages")

            # Aggregate per author: first_seen, last_seen, msg_count
            agg = (
                table.group_by("author_uuid")
                .aggregate(
                    first_seen=table.ts.min(),
                    last_seen=table.ts.max(),
                    msg_count=table.ts.count(),
                )
                .filter(lambda t: t.msg_count >= min_messages)
                .order_by(("last_seen", False))
            )

            rows = agg.execute()

        if rows.empty:
            logger.debug("No authors found with >= %d messages", min_messages)
            return []

        # Build name lookup from profiles directory
        name_map = _build_author_name_map(profiles_dir) if profiles_dir else {}

        results: list[AuthorHealth] = []
        for row in rows.itertuples(index=False):
            last_seen_dt = row.last_seen
            if hasattr(last_seen_dt, "to_pydatetime"):
                last_seen_dt = last_seen_dt.to_pydatetime()
            first_seen_dt = row.first_seen
            if hasattr(first_seen_dt, "to_pydatetime"):
                first_seen_dt = first_seen_dt.to_pydatetime()

            # Make timezone-aware if naive
            if last_seen_dt.tzinfo is None:
                last_seen_dt = last_seen_dt.replace(tzinfo=UTC)
            if first_seen_dt.tzinfo is None:
                first_seen_dt = first_seen_dt.replace(tzinfo=UTC)

            days_since = (now - last_seen_dt).days

            results.append(
                AuthorHealth(
                    author_uuid=row.author_uuid,
                    author_name=name_map.get(row.author_uuid, row.author_uuid[:8]),
                    first_seen=first_seen_dt,
                    last_seen=last_seen_dt,
                    msg_count=int(row.msg_count),
                    days_since_last=max(0, days_since),
                    status=_classify_status(max(0, days_since)),
                )
            )

        # Sort by days_since_last descending (ghosts first)
        results.sort(key=lambda a: a.days_since_last, reverse=True)
        return results

    except Exception as e:
        logger.warning("Failed to generate connection health data: %s", e)
        return []


def _build_author_name_map(profiles_dir: Path | None) -> dict[str, str]:
    """Build a mapping from author_uuid to display name from profiles directory."""
    if not profiles_dir or not profiles_dir.exists():
        return {}

    name_map: dict[str, str] = {}
    try:
        import frontmatter

        for author_dir in profiles_dir.iterdir():
            if not author_dir.is_dir():
                continue
            uuid = author_dir.name
            candidates = [p for p in author_dir.glob("*.md") if p.name != "index.md"]
            if candidates:
                profile_path = max(candidates, key=lambda p: p.stat().st_mtime_ns)
                post = frontmatter.load(str(profile_path))
                name = post.metadata.get("name", uuid[:8])
                name_map[uuid] = name
    except Exception as e:
        logger.warning("Failed to read profiles for name resolution: %s", e)

    return name_map


def compute_summary_stats(entries: list[AuthorHealth]) -> dict[str, Any]:
    """Compute summary statistics from health entries.

    Returns:
        Dict with total_contacts, status_counts, avg_silence_days, etc.

    """
    if not entries:
        return {
            "total_contacts": 0,
            "status_counts": {},
            "avg_silence_days": 0,
            "total_messages": 0,
        }

    status_counts: dict[str, int] = {}
    for entry in entries:
        status_counts[entry.status] = status_counts.get(entry.status, 0) + 1

    return {
        "total_contacts": len(entries),
        "status_counts": status_counts,
        "avg_silence_days": round(sum(e.days_since_last for e in entries) / len(entries)),
        "total_messages": sum(e.msg_count for e in entries),
    }
