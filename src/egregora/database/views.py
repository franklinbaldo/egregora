"""View registry for SQL query optimization.

This module provides materialized views for common pipeline queries,
improving performance by pre-computing frequently accessed patterns.

Usage:
    from egregora.database.views import ViewRegistry, register_common_views

    # Create registry
    registry = ViewRegistry(connection)

    # Register common views
    register_common_views(registry, table_name="messages")

    # Use materialized views
    author_stats = registry.query("author_message_counts")
    media_messages = registry.query("messages_with_media")
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import duckdb
import ibis
from ibis.expr.types import Table

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ViewDefinition:
    """Definition of a database view.

    Attributes:
        name: Unique view identifier
        sql: SQL query defining the view
        materialized: Whether to materialize (cache) the view
        dependencies: List of tables/views this depends on
        description: Human-readable description
    """

    name: str
    sql: str
    materialized: bool = False
    dependencies: tuple[str, ...] = ()
    description: str = ""


@dataclass
class ViewRegistry:
    """Registry for managing database views and materialized views.

    Provides a centralized way to define, create, and query views
    for common pipeline patterns. Supports materialized views for
    performance optimization.

    Attributes:
        connection: DuckDB connection
        views: Registered view definitions

    Example:
        >>> conn = duckdb.connect()
        >>> registry = ViewRegistry(conn)
        >>> registry.register(ViewDefinition(
        ...     name="active_authors",
        ...     sql="SELECT author, COUNT(*) as msg_count FROM messages GROUP BY author",
        ...     materialized=True,
        ... ))
        >>> registry.create_all()
        >>> results = registry.query("active_authors")
    """

    connection: duckdb.DuckDBPyConnection
    views: dict[str, ViewDefinition] = field(default_factory=dict)

    def register(self, view: ViewDefinition) -> None:
        """Register a view definition.

        Args:
            view: View definition to register

        Raises:
            ValueError: If view name is already registered
        """
        if view.name in self.views:
            msg = f"View '{view.name}' is already registered"
            raise ValueError(msg)

        self.views[view.name] = view
        logger.debug("Registered view: %s (materialized=%s)", view.name, view.materialized)

    def register_many(self, views: list[ViewDefinition]) -> None:
        """Register multiple view definitions.

        Args:
            views: List of view definitions
        """
        for view in views:
            self.register(view)

    def create(self, name: str, *, force: bool = False) -> None:
        """Create a view in the database.

        Args:
            name: View name
            force: If True, drop existing view before creating

        Raises:
            KeyError: If view not registered
        """
        if name not in self.views:
            msg = f"View '{name}' not registered"
            raise KeyError(msg)

        view = self.views[name]

        # Drop existing view if force=True
        if force:
            try:
                self.connection.execute(f"DROP VIEW IF EXISTS {view.name}")
                if view.materialized:
                    self.connection.execute(f"DROP TABLE IF EXISTS {view.name}")
            except duckdb.Error:
                pass  # View doesn't exist, that's fine

        # Create view or materialized view
        try:
            if view.materialized:
                # DuckDB doesn't support MATERIALIZED VIEW syntax
                # Use CREATE TABLE AS instead
                self.connection.execute(f"CREATE TABLE IF NOT EXISTS {view.name} AS {view.sql}")
                logger.info("Created materialized view: %s", view.name)
            else:
                self.connection.execute(f"CREATE VIEW IF NOT EXISTS {view.name} AS {view.sql}")
                logger.info("Created view: %s", view.name)
        except duckdb.Error as e:
            logger.exception("Failed to create view '%s': %s", view.name, e)
            raise

    def create_all(self, *, force: bool = False) -> None:
        """Create all registered views in dependency order.

        Args:
            force: If True, drop existing views before creating
        """
        # Topological sort based on dependencies
        sorted_views = self._topological_sort()

        for view_name in sorted_views:
            self.create(view_name, force=force)

        logger.info("Created %d views", len(sorted_views))

    def refresh(self, name: str) -> None:
        """Refresh a materialized view by re-executing its query.

        Args:
            name: View name to refresh

        Raises:
            KeyError: If view not registered
            ValueError: If view is not materialized
        """
        if name not in self.views:
            msg = f"View '{name}' not registered"
            raise KeyError(msg)

        view = self.views[name]

        if not view.materialized:
            msg = f"View '{name}' is not materialized (cannot refresh regular views)"
            raise ValueError(msg)

        # Drop and recreate the materialized view
        try:
            self.connection.execute(f"DROP TABLE IF EXISTS {view.name}")
            self.connection.execute(f"CREATE TABLE {view.name} AS {view.sql}")
            logger.info("Refreshed materialized view: %s", view.name)
        except duckdb.Error as e:
            logger.exception("Failed to refresh view '%s': %s", view.name, e)
            raise

    def refresh_all(self) -> None:
        """Refresh all materialized views in dependency order."""
        materialized_views = [
            name for name, view in self.views.items() if view.materialized
        ]

        # Sort by dependencies
        sorted_views = self._topological_sort()
        materialized_sorted = [v for v in sorted_views if v in materialized_views]

        for view_name in materialized_sorted:
            self.refresh(view_name)

        logger.info("Refreshed %d materialized views", len(materialized_sorted))

    def query(self, name: str) -> Any:
        """Query a view and return results.

        Args:
            name: View name

        Returns:
            Query results as pandas DataFrame

        Raises:
            KeyError: If view not registered or doesn't exist in database
        """
        if name not in self.views:
            msg = f"View '{name}' not registered"
            raise KeyError(msg)

        try:
            return self.connection.execute(f"SELECT * FROM {name}").fetchdf()
        except duckdb.Error as e:
            logger.exception("Failed to query view '%s': %s", name, e)
            raise

    def query_ibis(self, name: str, backend: ibis.BaseBackend) -> Table:
        """Query a view and return as Ibis table.

        Args:
            name: View name
            backend: Ibis backend connected to same database

        Returns:
            Ibis table expression

        Raises:
            KeyError: If view not registered
        """
        if name not in self.views:
            msg = f"View '{name}' not registered"
            raise KeyError(msg)

        return backend.table(name)

    def drop(self, name: str) -> None:
        """Drop a view from the database.

        Args:
            name: View name

        Raises:
            KeyError: If view not registered
        """
        if name not in self.views:
            msg = f"View '{name}' not registered"
            raise KeyError(msg)

        view = self.views[name]

        try:
            if view.materialized:
                self.connection.execute(f"DROP TABLE IF EXISTS {view.name}")
            else:
                self.connection.execute(f"DROP VIEW IF EXISTS {view.name}")
            logger.info("Dropped view: %s", view.name)
        except duckdb.Error as e:
            logger.exception("Failed to drop view '%s': %s", view.name, e)
            raise

    def drop_all(self) -> None:
        """Drop all registered views."""
        for view_name in self.views:
            try:
                self.drop(view_name)
            except duckdb.Error:
                pass  # View doesn't exist, that's fine

    def list_views(self) -> list[str]:
        """List all registered view names.

        Returns:
            List of view names
        """
        return list(self.views.keys())

    def get_view(self, name: str) -> ViewDefinition:
        """Get a view definition by name.

        Args:
            name: View name

        Returns:
            View definition

        Raises:
            KeyError: If view not registered
        """
        if name not in self.views:
            msg = f"View '{name}' not registered"
            raise KeyError(msg)

        return self.views[name]

    def _topological_sort(self) -> list[str]:
        """Topological sort of views based on dependencies.

        Returns:
            List of view names in dependency order

        Raises:
            ValueError: If circular dependencies detected
        """
        # Kahn's algorithm
        in_degree = {name: 0 for name in self.views}
        adj_list = {name: [] for name in self.views}

        # Build adjacency list and in-degree counts
        for name, view in self.views.items():
            for dep in view.dependencies:
                if dep in self.views:  # Only track dependencies within registry
                    adj_list[dep].append(name)
                    in_degree[name] += 1

        # Find views with no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        sorted_views = []

        while queue:
            current = queue.pop(0)
            sorted_views.append(current)

            # Reduce in-degree for dependent views
            for neighbor in adj_list[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for circular dependencies
        if len(sorted_views) != len(self.views):
            msg = "Circular dependencies detected in view definitions"
            raise ValueError(msg)

        return sorted_views


def register_common_views(
    registry: ViewRegistry,
    table_name: str = "messages",
) -> None:
    """Register common views for pipeline optimization.

    Args:
        registry: ViewRegistry instance
        table_name: Name of the base messages table
    """
    views = [
        # Author statistics
        ViewDefinition(
            name="author_message_counts",
            sql=f"""
                SELECT
                    author,
                    COUNT(*) as message_count,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM {table_name}
                GROUP BY author
                ORDER BY message_count DESC
            """,
            materialized=True,
            dependencies=(table_name,),
            description="Message counts per author with temporal bounds",
        ),
        # Active authors (more than 1 message)
        ViewDefinition(
            name="active_authors",
            sql="""
                SELECT author, message_count
                FROM author_message_counts
                WHERE message_count > 1
                ORDER BY message_count DESC
            """,
            materialized=False,
            dependencies=("author_message_counts",),
            description="Authors with more than one message",
        ),
        # Messages with media
        ViewDefinition(
            name="messages_with_media",
            sql=f"""
                SELECT *
                FROM {table_name}
                WHERE media_path IS NOT NULL
                ORDER BY timestamp
            """,
            materialized=True,
            dependencies=(table_name,),
            description="Messages containing media attachments",
        ),
        # Hourly message distribution
        ViewDefinition(
            name="hourly_message_stats",
            sql=f"""
                SELECT
                    DATE_TRUNC('hour', timestamp) as hour,
                    COUNT(*) as message_count,
                    COUNT(DISTINCT author) as active_authors
                FROM {table_name}
                GROUP BY hour
                ORDER BY hour
            """,
            materialized=True,
            dependencies=(table_name,),
            description="Message counts and active authors per hour",
        ),
        # Daily message distribution
        ViewDefinition(
            name="daily_message_stats",
            sql=f"""
                SELECT
                    DATE_TRUNC('day', timestamp) as day,
                    COUNT(*) as message_count,
                    COUNT(DISTINCT author) as active_authors
                FROM {table_name}
                GROUP BY day
                ORDER BY day
            """,
            materialized=True,
            dependencies=(table_name,),
            description="Message counts and active authors per day",
        ),
    ]

    registry.register_many(views)
    logger.info("Registered %d common views", len(views))
