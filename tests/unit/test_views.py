"""Tests for database view registry."""

import duckdb
import ibis
import pytest

from egregora.database.views import ViewDefinition, ViewRegistry, register_common_views


@pytest.fixture
def connection():
    """Create in-memory DuckDB connection."""
    return duckdb.connect(":memory:")


@pytest.fixture
def backend(connection):
    """Create Ibis backend."""
    return ibis.duckdb.from_connection(connection)


@pytest.fixture
def sample_table(connection):
    """Create sample messages table."""
    connection.execute("""
        CREATE TABLE messages (
            timestamp TIMESTAMP,
            author VARCHAR,
            message VARCHAR,
            media_path VARCHAR
        )
    """)

    # Insert sample data
    connection.execute("""
        INSERT INTO messages VALUES
            ('2025-01-01 10:00:00', 'alice', 'Hello', NULL),
            ('2025-01-01 10:30:00', 'bob', 'Hi', '/media/img1.jpg'),
            ('2025-01-01 11:00:00', 'alice', 'How are you?', NULL),
            ('2025-01-01 11:30:00', 'charlie', 'Good morning', NULL),
            ('2025-01-01 12:00:00', 'bob', 'Nice day', '/media/img2.jpg'),
            ('2025-01-02 09:00:00', 'alice', 'New day', NULL)
    """)

    return connection


@pytest.fixture
def registry(connection):
    """Create ViewRegistry instance."""
    return ViewRegistry(connection)


class TestViewDefinition:
    """Tests for ViewDefinition dataclass."""

    def test_create_minimal(self) -> None:
        """ViewDefinition can be created with minimal fields."""
        view = ViewDefinition(
            name="test_view",
            sql="SELECT * FROM messages",
        )

        assert view.name == "test_view"
        assert view.sql == "SELECT * FROM messages"
        assert view.materialized is False
        assert view.dependencies == ()
        assert view.description == ""

    def test_create_full(self) -> None:
        """ViewDefinition can be created with all fields."""
        view = ViewDefinition(
            name="test_view",
            sql="SELECT * FROM messages",
            materialized=True,
            dependencies=("messages", "users"),
            description="Test view",
        )

        assert view.materialized is True
        assert view.dependencies == ("messages", "users")
        assert view.description == "Test view"

    def test_immutable(self) -> None:
        """ViewDefinition is immutable (frozen)."""
        view = ViewDefinition(name="test", sql="SELECT 1")

        with pytest.raises(AttributeError):
            view.name = "changed"  # type: ignore[misc]


class TestViewRegistry:
    """Tests for ViewRegistry."""

    def test_register_view(self, registry: ViewRegistry) -> None:
        """register() adds view to registry."""
        view = ViewDefinition(name="test_view", sql="SELECT 1")

        registry.register(view)

        assert "test_view" in registry.views
        assert registry.views["test_view"] == view

    def test_register_duplicate_raises(self, registry: ViewRegistry) -> None:
        """register() raises ValueError for duplicate names."""
        view1 = ViewDefinition(name="test_view", sql="SELECT 1")
        view2 = ViewDefinition(name="test_view", sql="SELECT 2")

        registry.register(view1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(view2)

    def test_register_many(self, registry: ViewRegistry) -> None:
        """register_many() registers multiple views."""
        views = [
            ViewDefinition(name="view1", sql="SELECT 1"),
            ViewDefinition(name="view2", sql="SELECT 2"),
        ]

        registry.register_many(views)

        assert len(registry.views) == 2
        assert "view1" in registry.views
        assert "view2" in registry.views

    def test_create_view(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """create() creates view in database."""
        registry = ViewRegistry(sample_table)
        view = ViewDefinition(
            name="alice_messages",
            sql="SELECT * FROM messages WHERE author = 'alice'",
        )

        registry.register(view)
        registry.create("alice_messages")

        # Verify view exists
        result = sample_table.execute("SELECT COUNT(*) FROM alice_messages").fetchone()
        assert result[0] == 3  # alice has 3 messages

    def test_create_materialized_view(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """create() creates materialized view (table) in database."""
        registry = ViewRegistry(sample_table)
        view = ViewDefinition(
            name="author_counts",
            sql="SELECT author, COUNT(*) as count FROM messages GROUP BY author",
            materialized=True,
        )

        registry.register(view)
        registry.create("author_counts")

        # Verify materialized view exists as table
        result = sample_table.execute("SELECT * FROM author_counts ORDER BY count DESC").fetchall()
        assert len(result) == 3  # 3 authors
        assert result[0][0] == "alice"  # alice has most messages
        assert result[0][1] == 3

    def test_create_nonexistent_raises(self, registry: ViewRegistry) -> None:
        """create() raises KeyError for unregistered view."""
        with pytest.raises(KeyError, match="not registered"):
            registry.create("nonexistent")

    def test_create_all(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """create_all() creates all views in dependency order."""
        registry = ViewRegistry(sample_table)

        # Register views with dependencies
        registry.register_many(
            [
                ViewDefinition(
                    name="base_stats",
                    sql="SELECT author, COUNT(*) as count FROM messages GROUP BY author",
                    materialized=True,
                ),
                ViewDefinition(
                    name="top_authors",
                    sql="SELECT author FROM base_stats WHERE count > 1 ORDER BY count DESC",
                    dependencies=("base_stats",),
                ),
            ]
        )

        registry.create_all()

        # Verify both views exist
        result1 = sample_table.execute("SELECT COUNT(*) FROM base_stats").fetchone()
        assert result1[0] == 3

        result2 = sample_table.execute("SELECT COUNT(*) FROM top_authors").fetchone()
        assert result2[0] == 2  # alice and bob have >1 messages

    def test_create_all_force(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """create_all(force=True) recreates existing views."""
        registry = ViewRegistry(sample_table)
        view = ViewDefinition(name="test_view", sql="SELECT 1 as value")

        registry.register(view)
        registry.create_all()

        # Verify initial view
        result1 = sample_table.execute("SELECT value FROM test_view").fetchone()
        assert result1[0] == 1

        # Change view definition and recreate
        registry.views["test_view"] = ViewDefinition(name="test_view", sql="SELECT 2 as value")
        registry.create_all(force=True)

        # Verify updated view
        result2 = sample_table.execute("SELECT value FROM test_view").fetchone()
        assert result2[0] == 2

    def test_refresh_materialized_view(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """refresh() updates materialized view with fresh data."""
        registry = ViewRegistry(sample_table)
        view = ViewDefinition(
            name="message_count",
            sql="SELECT COUNT(*) as count FROM messages",
            materialized=True,
        )

        registry.register(view)
        registry.create("message_count")

        # Initial count
        result1 = sample_table.execute("SELECT count FROM message_count").fetchone()
        assert result1[0] == 6

        # Insert more messages
        sample_table.execute("INSERT INTO messages VALUES ('2025-01-02 10:00:00', 'dave', 'Hi', NULL)")

        # Refresh materialized view
        registry.refresh("message_count")

        # Verify updated count
        result2 = sample_table.execute("SELECT count FROM message_count").fetchone()
        assert result2[0] == 7

    def test_refresh_regular_view_raises(self, registry: ViewRegistry) -> None:
        """refresh() raises ValueError for non-materialized views."""
        view = ViewDefinition(name="test_view", sql="SELECT 1")

        registry.register(view)

        with pytest.raises(ValueError, match="not materialized"):
            registry.refresh("test_view")

    def test_refresh_all(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """refresh_all() updates all materialized views."""
        registry = ViewRegistry(sample_table)

        # Register multiple materialized views
        registry.register_many(
            [
                ViewDefinition(
                    name="total_messages",
                    sql="SELECT COUNT(*) as count FROM messages",
                    materialized=True,
                ),
                ViewDefinition(
                    name="total_authors",
                    sql="SELECT COUNT(DISTINCT author) as count FROM messages",
                    materialized=True,
                ),
            ]
        )

        registry.create_all()

        # Insert more data
        sample_table.execute("INSERT INTO messages VALUES ('2025-01-02 11:00:00', 'eve', 'Hello', NULL)")

        # Refresh all
        registry.refresh_all()

        # Verify both views updated
        result1 = sample_table.execute("SELECT count FROM total_messages").fetchone()
        assert result1[0] == 7

        result2 = sample_table.execute("SELECT count FROM total_authors").fetchone()
        assert result2[0] == 4

    def test_query(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """query() returns results as DataFrame."""
        registry = ViewRegistry(sample_table)
        view = ViewDefinition(
            name="alice_messages",
            sql="SELECT * FROM messages WHERE author = 'alice' ORDER BY timestamp",
        )

        registry.register(view)
        registry.create("alice_messages")

        result = registry.query("alice_messages")

        assert len(result) == 3
        assert result["author"].tolist() == ["alice", "alice", "alice"]

    def test_query_nonexistent_raises(self, registry: ViewRegistry) -> None:
        """query() raises KeyError for unregistered view."""
        with pytest.raises(KeyError, match="not registered"):
            registry.query("nonexistent")

    def test_query_ibis(self, sample_table: duckdb.DuckDBPyConnection, backend: ibis.BaseBackend) -> None:
        """query_ibis() returns Ibis table."""
        registry = ViewRegistry(sample_table)
        view = ViewDefinition(
            name="test_view",
            sql="SELECT author, COUNT(*) as count FROM messages GROUP BY author",
        )

        registry.register(view)
        registry.create("test_view")

        table = registry.query_ibis("test_view", backend)

        assert isinstance(table, ibis.expr.types.Table)
        assert "author" in table.columns
        assert "count" in table.columns

    def test_drop_view(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """drop() removes view from database."""
        registry = ViewRegistry(sample_table)
        view = ViewDefinition(name="test_view", sql="SELECT 1")

        registry.register(view)
        registry.create("test_view")

        # Verify view exists
        result1 = sample_table.execute("SELECT * FROM test_view").fetchone()
        assert result1[0] == 1

        # Drop view
        registry.drop("test_view")

        # Verify view removed
        with pytest.raises(duckdb.CatalogException):
            sample_table.execute("SELECT * FROM test_view")

    def test_drop_all(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """drop_all() removes all views."""
        registry = ViewRegistry(sample_table)
        registry.register_many(
            [
                ViewDefinition(name="view1", sql="SELECT 1"),
                ViewDefinition(name="view2", sql="SELECT 2"),
            ]
        )

        registry.create_all()
        registry.drop_all()

        # Verify both views removed
        with pytest.raises(duckdb.CatalogException):
            sample_table.execute("SELECT * FROM view1")

        with pytest.raises(duckdb.CatalogException):
            sample_table.execute("SELECT * FROM view2")

    def test_list_views(self, registry: ViewRegistry) -> None:
        """list_views() returns all registered view names."""
        registry.register_many(
            [
                ViewDefinition(name="view1", sql="SELECT 1"),
                ViewDefinition(name="view2", sql="SELECT 2"),
            ]
        )

        views = registry.list_views()

        assert set(views) == {"view1", "view2"}

    def test_get_view(self, registry: ViewRegistry) -> None:
        """get_view() returns view definition."""
        view = ViewDefinition(name="test_view", sql="SELECT 1")
        registry.register(view)

        retrieved = registry.get_view("test_view")

        assert retrieved == view

    def test_get_view_nonexistent_raises(self, registry: ViewRegistry) -> None:
        """get_view() raises KeyError for unregistered view."""
        with pytest.raises(KeyError, match="not registered"):
            registry.get_view("nonexistent")

    def test_topological_sort_simple(self, registry: ViewRegistry) -> None:
        """_topological_sort() orders views by dependencies."""
        registry.register_many(
            [
                ViewDefinition(name="base", sql="SELECT 1"),
                ViewDefinition(name="derived", sql="SELECT * FROM base", dependencies=("base",)),
            ]
        )

        sorted_views = registry._topological_sort()

        # base must come before derived
        assert sorted_views.index("base") < sorted_views.index("derived")

    def test_topological_sort_complex(self, registry: ViewRegistry) -> None:
        """_topological_sort() handles complex dependency graphs."""
        registry.register_many(
            [
                ViewDefinition(name="a", sql="SELECT 1"),
                ViewDefinition(name="b", sql="SELECT 1"),
                ViewDefinition(name="c", sql="SELECT * FROM a", dependencies=("a",)),
                ViewDefinition(name="d", sql="SELECT * FROM b, c", dependencies=("b", "c")),
            ]
        )

        sorted_views = registry._topological_sort()

        # Verify all dependencies satisfied
        assert sorted_views.index("a") < sorted_views.index("c")
        assert sorted_views.index("b") < sorted_views.index("d")
        assert sorted_views.index("c") < sorted_views.index("d")

    def test_topological_sort_circular_raises(self, registry: ViewRegistry) -> None:
        """_topological_sort() raises ValueError for circular dependencies."""
        registry.register_many(
            [
                ViewDefinition(name="view1", sql="SELECT * FROM view2", dependencies=("view2",)),
                ViewDefinition(name="view2", sql="SELECT * FROM view1", dependencies=("view1",)),
            ]
        )

        with pytest.raises(ValueError, match="Circular dependencies"):
            registry._topological_sort()


class TestRegisterCommonViews:
    """Tests for register_common_views()."""

    def test_register_common_views(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """register_common_views() registers standard views."""
        registry = ViewRegistry(sample_table)

        register_common_views(registry, table_name="messages")

        # Verify expected views registered
        views = registry.list_views()
        assert "author_message_counts" in views
        assert "active_authors" in views
        assert "messages_with_media" in views
        assert "hourly_message_stats" in views
        assert "daily_message_stats" in views

    def test_author_message_counts(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """author_message_counts view works correctly."""
        registry = ViewRegistry(sample_table)
        register_common_views(registry)
        registry.create_all()

        result = registry.query("author_message_counts")

        assert len(result) == 3  # 3 authors
        assert result.loc[result["author"] == "alice", "message_count"].iloc[0] == 3
        assert result.loc[result["author"] == "bob", "message_count"].iloc[0] == 2

    def test_active_authors(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """active_authors view filters authors with >1 message."""
        registry = ViewRegistry(sample_table)
        register_common_views(registry)
        registry.create_all()

        result = registry.query("active_authors")

        assert len(result) == 2  # alice and bob
        assert "charlie" not in result["author"].tolist()

    def test_messages_with_media(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """messages_with_media view filters messages with attachments."""
        registry = ViewRegistry(sample_table)
        register_common_views(registry)
        registry.create_all()

        result = registry.query("messages_with_media")

        assert len(result) == 2  # 2 messages with media
        assert all(result["media_path"].notna())

    def test_hourly_message_stats(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """hourly_message_stats view aggregates by hour."""
        registry = ViewRegistry(sample_table)
        register_common_views(registry)
        registry.create_all()

        result = registry.query("hourly_message_stats")

        # We have messages in: 10:00, 11:00, 12:00 (Jan 1), 09:00 (Jan 2)
        assert len(result) == 4
        assert all(result["message_count"] > 0)

    def test_daily_message_stats(self, sample_table: duckdb.DuckDBPyConnection) -> None:
        """daily_message_stats view aggregates by day."""
        registry = ViewRegistry(sample_table)
        register_common_views(registry)
        registry.create_all()

        result = registry.query("daily_message_stats")

        # We have messages on 2 days
        assert len(result) == 2
        assert result.loc[0, "message_count"] == 5  # Jan 1
        assert result.loc[1, "message_count"] == 1  # Jan 2
