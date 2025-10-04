"""Tests for backlog cost estimation."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.backlog.estimator import estimate_costs
from egregora.backlog.scanner import PendingDay
from egregora.config import BacklogConfig


def _pending_day(day: date, messages: int, urls: int) -> PendingDay:
    return PendingDay(
        date=day,
        zip_path=Path(f"/tmp/{day.isoformat()}.zip"),
        newsletter_path=Path(f"/tmp/{day.isoformat()}.md"),
        already_processed=False,
        message_count=messages,
        url_count=urls,
        participant_count=3,
    )


def test_estimate_costs_basic() -> None:
    config = BacklogConfig()
    days = [_pending_day(date(2024, 10, 1), messages=50, urls=5)]
    estimate = estimate_costs(days, config)
    assert estimate.total_days == 1
    assert estimate.total_messages == 50
    assert estimate.total_urls == 5
    assert estimate.estimated_cost_usd > 0


def test_estimate_considers_enrichment() -> None:
    config = BacklogConfig()
    days = [_pending_day(date(2024, 10, 1), messages=10, urls=10)]
    estimate = estimate_costs(days, config)
    per_day = estimate.per_day[0]
    baseline = 500 + 10 * 35
    expected_tokens = baseline + 10 * 120
    assert per_day.estimated_tokens == expected_tokens


def test_estimate_calculates_time() -> None:
    config = BacklogConfig()
    days = [_pending_day(date(2024, 10, 1), messages=20, urls=0)]
    estimate = estimate_costs(days, config)
    assert estimate.estimated_time_seconds > 0
    assert estimate.per_day[0].estimated_time_seconds == round(max(20, 1) * 0.08, 2)


def test_estimate_multiple_days() -> None:
    config = BacklogConfig()
    days = [
        _pending_day(date(2024, 10, 1), messages=30, urls=2),
        _pending_day(date(2024, 10, 2), messages=40, urls=1),
    ]
    estimate = estimate_costs(days, config)
    assert estimate.total_days == 2
    assert len(estimate.per_day) == 2
