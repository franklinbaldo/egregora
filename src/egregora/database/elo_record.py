"""Data models for ELO rating records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class ComparisonRecord:
    """Record of a pairwise comparison."""

    comparison_id: str
    post_a_slug: str
    post_b_slug: str
    winner: str
    rating_a_before: float
    rating_b_before: float
    rating_a_after: float
    rating_b_after: float
    timestamp: datetime
    reader_feedback: str | None
