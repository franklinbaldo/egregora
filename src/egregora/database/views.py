"""Common view transformations used throughout the pipeline.

The previous decorator-based registry added indirection without providing
meaningful flexibility. Callers now import the view builders they need
directly from this module or look them up via the ``COMMON_VIEWS`` mapping.
"""

from collections.abc import Callable
import logging

import ibis
from ibis.expr.types import Table

logger = logging.getLogger(__name__)

# Type alias for view builder functions
type ViewBuilder = Callable[[Table], Table]


def chunks_view(ir: Table) -> Table:
    """Chunk conversations into sequential windows.

    Adds a ``chunk_idx`` column with row numbers partitioned by ``thread_id``
    and ordered by ``ts``.
    """

    win = ibis.window(group_by="thread_id", order_by="ts")
    return ir.mutate(chunk_idx=ibis.row_number().over(win))


def chunks_sql(ir: Table) -> Table:
    """Optimized chunking with raw SQL.

    Same as :func:`chunks_view` but uses SQL for better performance on large
    datasets.
    """

    return ir.sql(
        """
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY thread_id
                ORDER BY ts
            ) AS chunk_idx
        FROM {}
        """
    )


def messages_with_media_view(ir: Table) -> Table:
    """Filter to messages containing media."""

    return ir.filter(ir.media_url.notnull())


def messages_with_text_view(ir: Table) -> Table:
    """Filter to messages containing non-empty text."""

    return ir.filter(ir.text.notnull() & (ir.text != ""))


def hourly_aggregates_view(ir: Table) -> Table:
    """Aggregate messages by hour."""

    return (
        ir.mutate(hour=ir.ts.truncate("hour"))
        .group_by("hour")
        .agg(
            message_count=ibis._.count(),
            unique_authors=ibis._.author_uuid.nunique(),
            first_message=ibis._.ts.min(),
            last_message=ibis._.ts.max(),
        )
        .order_by("hour")
    )


def daily_aggregates_view(ir: Table) -> Table:
    """Aggregate messages by day."""

    return (
        ir.mutate(day=ir.ts.truncate("day"))
        .group_by("day")
        .agg(
            message_count=ibis._.count(),
            unique_authors=ibis._.author_uuid.nunique(),
            first_message=ibis._.ts.min(),
            last_message=ibis._.ts.max(),
        )
        .order_by("day")
    )


COMMON_VIEWS: dict[str, ViewBuilder] = {
    "chunks": chunks_view,
    "chunks_optimized": chunks_sql,
    "messages_with_media": messages_with_media_view,
    "messages_with_text": messages_with_text_view,
    "hourly_aggregates": hourly_aggregates_view,
    "daily_aggregates": daily_aggregates_view,
}


def get_view_builder(name: str) -> ViewBuilder:
    """Return a view builder by name.

    Raises
    ------
    KeyError
        If the requested view name is not defined in ``COMMON_VIEWS``.
    """

    try:
        return COMMON_VIEWS[name]
    except KeyError as exc:  # pragma: no cover - defensive logging path
        logger.error("Unknown view requested: %s", name)
        raise KeyError(f"Unknown view: {name}") from exc


def list_common_views() -> list[str]:
    """Return the sorted list of known view names."""

    return sorted(COMMON_VIEWS)


__all__ = [
    "COMMON_VIEWS",
    "ViewBuilder",
    "chunks_sql",
    "chunks_view",
    "daily_aggregates_view",
    "get_view_builder",
    "hourly_aggregates_view",
    "list_common_views",
    "messages_with_media_view",
    "messages_with_text_view",
]
