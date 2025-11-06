"""Generic pipeline utilities for grouping and organizing messages."""

import logging
from pathlib import Path
import ibis
from ibis.expr.types import Table
from egregora.constants import Limits
from egregora.sources.whatsapp import discover_chat_file, process_whatsapp_export

logger = logging.getLogger(__name__)


def period_has_posts(period_key: str, posts_dir: Path) -> bool:
    """Check if posts already exist for this period."""
    if not posts_dir.exists():
        return False
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
        week_num = table.timestamp.week_of_year()
        iso_year = ibis.cases(
            ((week_num >= 52) & (table.timestamp.month() == 1), table.timestamp.year() - 1),
            ((week_num == 1) & (table.timestamp.month() == 12), table.timestamp.year() + 1),
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
        year_str = table.timestamp.year().cast("string")
        month_num = table.timestamp.month()
        month_str = ibis.ifelse(
            month_num < Limits.SINGLE_DIGIT_THRESHOLD,
            ibis.literal("0") + month_num.cast("string"),
            month_num.cast("string"),
        )
        table = table.mutate(period=year_str + ibis.literal("-") + month_str)
    else:
        msg = f"Unknown period: {period}"
        raise ValueError(msg)
    grouped = {}
    period_values = sorted(table.select("period").distinct().execute()["period"].tolist())
    for period_value in period_values:
        period_table = table.filter(table.period == period_value).drop("period")
        grouped[period_value] = period_table
    return grouped
