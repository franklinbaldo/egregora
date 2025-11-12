"""Canonical view registry for pipeline stages.

Stages reference views by name, not file paths. This allows:
- SQL optimization when needed (performance)
- Centralized view definitions
- Easy testing (swap views for mocks)

This module provides a decorator-based registry for pipeline view builders.
Unlike src/egregora/database/views.py (SQL materialized views for query optimization),
this registry focuses on pipeline stage transformations that can be written in
either Ibis or SQL.

Usage:
    from egregora.database.views import views

    # Register a view using decorator
    @views.register("chunks")
    def chunks_view(ir: ibis.Table) -> ibis.Table:
        return ir.mutate(chunk_idx=ibis.row_number().over(...))

    # Use in pipeline stage
    chunks_builder = views.get("chunks")
    result = chunks_builder(ir_table)

    # Or use SQL for performance
    @views.register("chunks_optimized")
    def chunks_sql(ir: ibis.Table) -> ibis.Table:
        return ir.sql("SELECT *, ROW_NUMBER() OVER (...) FROM ir")
"""

import logging
from collections.abc import Callable

import ibis
from ibis.expr.types import Table

logger = logging.getLogger(__name__)

# Type alias for view builder functions
type ViewBuilder = Callable[[Table], Table]


class ViewRegistry:
    """Registry of canonical pipeline views.

    Provides a centralized registry for pipeline view builders that transform
    Ibis tables. View builders can use either Ibis expressions or raw SQL
    for performance-critical operations.

    Attributes:
        _views: Dictionary mapping view names to builder functions

    Example:
        >>> registry = ViewRegistry()
        >>>
        >>> @registry.register("enriched")
        >>> def enriched_view(ir: Table) -> Table:
        ...     return ir.filter(ir.text.notnull())
        >>>
        >>> builder = registry.get("enriched")
        >>> result = builder(my_table)

    """

    def __init__(self) -> None:
        """Initialize empty view registry."""
        self._views: dict[str, ViewBuilder] = {}
        logger.debug("Initialized ViewRegistry")

    def register(self, name: str) -> Callable[[ViewBuilder], ViewBuilder]:
        """Decorator to register a view builder.

        Args:
            name: Unique view identifier

        Returns:
            Decorator function that registers the view builder

        Raises:
            ValueError: If view name is already registered

        Example:
            >>> @views.register("my_view")
            >>> def my_view_builder(ir: Table) -> Table:
            ...     return ir.limit(100)

        """

        def decorator(func: ViewBuilder) -> ViewBuilder:
            if name in self._views:
                msg = f"View '{name}' is already registered"
                raise ValueError(msg)

            self._views[name] = func
            logger.debug("Registered view: %s (function: %s)", name, func.__name__)
            return func

        return decorator

    def register_function(self, name: str, func: ViewBuilder) -> None:
        """Register a view builder function directly (without decorator).

        Args:
            name: Unique view identifier
            func: View builder function

        Raises:
            ValueError: If view name is already registered

        Example:
            >>> def chunks(ir: Table) -> Table:
            ...     return ir.mutate(chunk_idx=...)
            >>> views.register_function("chunks", chunks)

        """
        if name in self._views:
            msg = f"View '{name}' is already registered"
            raise ValueError(msg)

        self._views[name] = func
        logger.debug("Registered view: %s (function: %s)", name, func.__name__)

    def get(self, name: str) -> ViewBuilder:
        """Get view builder by name.

        Args:
            name: View identifier

        Returns:
            View builder function

        Raises:
            KeyError: If view not found

        Example:
            >>> builder = views.get("chunks")
            >>> result = builder(ir_table)

        """
        if name not in self._views:
            msg = f"View not found: {name}"
            raise KeyError(msg)

        return self._views[name]

    def has(self, name: str) -> bool:
        """Check if view is registered.

        Args:
            name: View identifier

        Returns:
            True if view exists, False otherwise

        """
        return name in self._views

    def list_views(self) -> list[str]:
        """List all registered view names.

        Returns:
            Sorted list of view names

        """
        return sorted(self._views.keys())

    def unregister(self, name: str) -> None:
        """Remove a view from the registry.

        Args:
            name: View identifier

        Raises:
            KeyError: If view not found

        """
        if name not in self._views:
            msg = f"View not found: {name}"
            raise KeyError(msg)

        del self._views[name]
        logger.debug("Unregistered view: %s", name)

    def clear(self) -> None:
        """Remove all views from the registry."""
        count = len(self._views)
        self._views.clear()
        logger.debug("Cleared %d views from registry", count)


# Global singleton registry for pipeline views
views = ViewRegistry()


# ============================================================================
# Common Pipeline Views
# ============================================================================
# These are standard view builders for common pipeline operations.
# Custom projects can register additional views as needed.


@views.register("chunks")
def chunks_view(ir: Table) -> Table:
    """Chunk conversations into sequential windows.

    Adds a chunk_idx column with row numbers partitioned by thread_id
    and ordered by timestamp.

    Args:
        ir: IR v1 table with thread_id and ts columns

    Returns:
        IR table with added chunk_idx column

    """
    win = ibis.window(group_by="thread_id", order_by="ts")
    return ir.mutate(chunk_idx=ibis.row_number().over(win))


@views.register("chunks_optimized")
def chunks_sql(ir: Table) -> Table:
    """Optimized chunking with raw SQL.

    Same as chunks_view but uses SQL for better performance on large datasets.

    Args:
        ir: IR v1 table with thread_id and ts columns

    Returns:
        IR table with added chunk_idx column

    """
    return ir.sql("""
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY thread_id
                ORDER BY ts
            ) AS chunk_idx
        FROM {}
    """)


@views.register("messages_with_media")
def messages_with_media_view(ir: Table) -> Table:
    """Filter to messages containing media.

    Args:
        ir: IR v1 table

    Returns:
        IR table filtered to messages with media_url not null

    """
    return ir.filter(ir.media_url.notnull())


@views.register("messages_with_text")
def messages_with_text_view(ir: Table) -> Table:
    """Filter to messages containing text.

    Args:
        ir: IR v1 table

    Returns:
        IR table filtered to messages with non-empty text

    """
    return ir.filter(ir.text.notnull() & (ir.text != ""))


@views.register("hourly_aggregates")
def hourly_aggregates_view(ir: Table) -> Table:
    """Aggregate messages by hour.

    Groups messages into hourly windows and computes:
    - Message count per hour
    - Unique authors per hour
    - First and last message timestamps

    Args:
        ir: IR v1 table with ts and author_uuid columns

    Returns:
        Aggregated table with hourly statistics

    """
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


@views.register("daily_aggregates")
def daily_aggregates_view(ir: Table) -> Table:
    """Aggregate messages by day.

    Groups messages into daily windows and computes:
    - Message count per day
    - Unique authors per day
    - First and last message timestamps

    Args:
        ir: IR v1 table with ts and author_uuid columns

    Returns:
        Aggregated table with daily statistics

    """
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


# Export public API
__all__ = [
    "ViewBuilder",
    "ViewRegistry",
    "views",
]
