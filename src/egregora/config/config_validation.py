from __future__ import annotations

from datetime import UTC, date

from dateutil import parser as date_parser


def parse_date_arg(value: str | None, name: str) -> date | None:
    """Parse a date string used by CLI flags."""
    if value is None:
        return None
    try:
        parsed = date_parser.isoparse(value)
        parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        return parsed.date()
    except (ValueError, TypeError) as exc:
        msg = f"Invalid date for {name}: {value!r}"
        raise ValueError(msg) from exc


def validate_retrieval_config(mode: str, nprobe: int | None, overfetch: int | None) -> str:
    """Validate retrieval mode and return the normalized choice."""
    normalized = (mode or "ann").lower()
    if normalized not in {"ann", "exact"}:
        msg = f"Unsupported retrieval mode: {mode}"
        raise ValueError(msg)

    if normalized == "exact":
        if nprobe is not None or overfetch is not None:
            msg = "nprobe/overfetch are only valid for ANN retrieval"
            raise ValueError(msg)
        return normalized

    return normalized
