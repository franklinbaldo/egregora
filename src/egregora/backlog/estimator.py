"""Cost estimation utilities for backlog processing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List

from ..config import BacklogConfig
from .scanner import PendingDay

TOKENS_PER_MESSAGE = 35
TOKENS_PER_URL = 120
BASE_TOKENS = 500
COST_PER_1K_TOKENS_USD = 0.002
SECONDS_PER_MESSAGE = 0.08


@dataclass(slots=True)
class DayEstimate:
    """Per-day metrics used in aggregated cost estimation."""

    date: date
    messages: int
    urls: int
    estimated_tokens: int
    estimated_cost_usd: float
    estimated_time_seconds: float


@dataclass(slots=True)
class CostEstimate:
    """Aggregated estimation result."""

    total_days: int
    total_messages: int
    total_urls: int
    total_tokens: int
    estimated_cost_usd: float
    estimated_time_seconds: float
    per_day: List[DayEstimate]


def _estimate_day(pending_day: PendingDay) -> DayEstimate:
    tokens = BASE_TOKENS + pending_day.message_count * TOKENS_PER_MESSAGE
    tokens += pending_day.url_count * TOKENS_PER_URL
    cost = (tokens / 1000.0) * COST_PER_1K_TOKENS_USD
    time_seconds = max(pending_day.message_count, 1) * SECONDS_PER_MESSAGE
    return DayEstimate(
        date=pending_day.date,
        messages=pending_day.message_count,
        urls=pending_day.url_count,
        estimated_tokens=int(tokens),
        estimated_cost_usd=round(cost, 4),
        estimated_time_seconds=round(time_seconds, 2),
    )


def estimate_costs(pending_days: Iterable[PendingDay], config: BacklogConfig) -> CostEstimate:
    """Estimate aggregated Gemini usage costs for *pending_days*."""

    per_day: List[DayEstimate] = []
    for day in pending_days:
        per_day.append(_estimate_day(day))

    total_tokens = sum(item.estimated_tokens for item in per_day)
    total_cost = sum(item.estimated_cost_usd for item in per_day)
    total_time = sum(item.estimated_time_seconds for item in per_day)

    return CostEstimate(
        total_days=len(per_day),
        total_messages=sum(item.messages for item in per_day),
        total_urls=sum(item.urls for item in per_day),
        total_tokens=total_tokens,
        estimated_cost_usd=round(total_cost, 4),
        estimated_time_seconds=round(total_time, 2),
        per_day=per_day,
    )


__all__ = ["CostEstimate", "DayEstimate", "estimate_costs"]
