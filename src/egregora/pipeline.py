"""Generic pipeline utilities for grouping and organizing messages."""

import logging
from pathlib import Path

import ibis
from ibis.expr.types import Table

from egregora.constants import Limits

# Backward compatibility: Re-export WhatsApp functions that were previously in this module
# These have been moved to egregora.sources.whatsapp.pipeline but we maintain the old
# import path for existing code that uses "from egregora.pipeline import ..."
from egregora.sources.whatsapp import (  # noqa: F401
    discover_chat_file,
    process_whatsapp_export,
)

logger = logging.getLogger(__name__)


def period_has_posts(period_key: str, posts_dir: Path) -> bool:
    """Check if posts already exist for this period."""
    if not posts_dir.exists():
        return False

    # Look for files matching {period_key}-*.md
    pattern = f"{period_key}-*.md"
    existing_posts = list(posts_dir.glob(pattern))

    return len(existing_posts) > 0


def group_by_period(table: Table, period: str = "day") -> dict[str, Table]:
    """Group Table by time period.

    Args:
        table: Table with timestamp column
        period: "day", "week", or "month"

    Returns:
        Dict mapping period string to Table

    """
    if table.count().execute() == 0:
        return {}

    if period == "day":
        table = table.mutate(period=table.timestamp.date().cast("string"))
    elif period == "week":
        # ISO week format: YYYY-Wnn
        # Use ISO week-year to handle weeks that cross calendar year boundaries
        # (e.g., 2024-W52 can include days from early January 2025)
        week_num = table.timestamp.week_of_year()

        # ISO week-year: if week number is 52/53 and month is January,
        # the ISO year is previous calendar year
        # if week number is 1 and month is December,
        # the ISO year is next calendar year
        iso_year = ibis.cases(
            ((week_num >= 52) & (table.timestamp.month() == 1), table.timestamp.year() - 1),  # noqa: PLR2004
            ((week_num == 1) & (table.timestamp.month() == 12), table.timestamp.year() + 1),  # noqa: PLR2004
            else_=table.timestamp.year(),
        )

        year_str = iso_year.cast("string")
        week_str = ibis.ifelse(
            week_num < Limits.SINGLE_DIGIT_THRESHOLD,
            ibis.literal("0") + week_num.cast("string"),
            week_num.cast("string"),
        )
        table = table.mutate(period=year_str + ibis.literal("-W") + week_str)
    elif period == "month":
        # Format: YYYY-MM
        year_str = table.timestamp.year().cast("string")
        month_num = table.timestamp.month()
        # Zero-pad month: use lpad to ensure 2 digits
        month_str = ibis.ifelse(
            month_num < Limits.SINGLE_DIGIT_THRESHOLD,
            ibis.literal("0") + month_num.cast("string"),
            month_num.cast("string"),
        )
        table = table.mutate(period=year_str + ibis.literal("-") + month_str)
    else:
        raise ValueError(f"Unknown period: {period}")

    grouped = {}
    # Get unique period values, sorted
    period_values = sorted(table.select("period").distinct().execute()["period"].tolist())

    for period_value in period_values:
        period_table = table.filter(table.period == period_value).drop("period")
        grouped[period_value] = period_table

    return grouped
