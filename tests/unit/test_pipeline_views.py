"""Tests for pipeline view registry (Priority C.1)."""

import ibis
import pytest
from ibis.expr.types import Table

from egregora.pipeline.views import ViewBuilder, ViewRegistry, views


class TestViewRegistry:
    """Tests for ViewRegistry class."""

    def test_init(self):
        """Test registry initialization."""
        registry = ViewRegistry()
        assert registry.list_views() == []

    def test_register_decorator(self):
        """Test registering view with decorator."""
        registry = ViewRegistry()

        @registry.register("test_view")
        def test_builder(ir: Table) -> Table:
            return ir.limit(10)

        assert registry.has("test_view")
        assert registry.get("test_view") == test_builder

    def test_register_function(self):
        """Test registering view with direct function call."""
        registry = ViewRegistry()

        def my_builder(ir: Table) -> Table:
            return ir.limit(5)

        registry.register_function("my_view", my_builder)

        assert registry.has("my_view")
        assert registry.get("my_view") == my_builder

    def test_register_duplicate_raises(self):
        """Test registering duplicate view name raises ValueError."""
        registry = ViewRegistry()

        @registry.register("duplicate")
        def first(ir: Table) -> Table:
            return ir

        with pytest.raises(ValueError, match="already registered"):
            registry.register("duplicate")(lambda ir: ir)

    def test_register_function_duplicate_raises(self):
        """Test registering duplicate with register_function raises."""
        registry = ViewRegistry()
        registry.register_function("dup", lambda ir: ir)

        with pytest.raises(ValueError, match="already registered"):
            registry.register_function("dup", lambda ir: ir)

    def test_get_missing_raises(self):
        """Test getting non-existent view raises KeyError."""
        registry = ViewRegistry()

        with pytest.raises(KeyError, match="View not found: missing"):
            registry.get("missing")

    def test_has(self):
        """Test has() method."""
        registry = ViewRegistry()
        assert not registry.has("nonexistent")

        registry.register_function("exists", lambda ir: ir)
        assert registry.has("exists")

    def test_list_views(self):
        """Test listing all registered views."""
        registry = ViewRegistry()

        registry.register_function("view_b", lambda ir: ir)
        registry.register_function("view_a", lambda ir: ir)
        registry.register_function("view_c", lambda ir: ir)

        # Should be sorted alphabetically
        assert registry.list_views() == ["view_a", "view_b", "view_c"]

    def test_unregister(self):
        """Test unregistering a view."""
        registry = ViewRegistry()
        registry.register_function("temp", lambda ir: ir)

        assert registry.has("temp")
        registry.unregister("temp")
        assert not registry.has("temp")

    def test_unregister_missing_raises(self):
        """Test unregistering non-existent view raises KeyError."""
        registry = ViewRegistry()

        with pytest.raises(KeyError, match="View not found: missing"):
            registry.unregister("missing")

    def test_clear(self):
        """Test clearing all views."""
        registry = ViewRegistry()
        registry.register_function("view1", lambda ir: ir)
        registry.register_function("view2", lambda ir: ir)

        assert len(registry.list_views()) == 2
        registry.clear()
        assert len(registry.list_views()) == 0

    def test_view_builder_execution(self):
        """Test executing a registered view builder."""
        registry = ViewRegistry()

        @registry.register("limit_10")
        def limit_builder(ir: Table) -> Table:
            return ir.limit(10)

        # Create sample table
        table = ibis.memtable({"id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]}, schema={"id": "int64"})

        # Execute view builder
        builder = registry.get("limit_10")
        result = builder(table)

        # Verify result
        df = result.execute()
        assert len(df) == 10

    def test_view_builder_with_filter(self):
        """Test view builder with filter operation."""
        registry = ViewRegistry()

        @registry.register("even_only")
        def even_filter(ir: Table) -> Table:
            return ir.filter(ir.value % 2 == 0)

        # Create sample table
        table = ibis.memtable({"value": [1, 2, 3, 4, 5, 6]}, schema={"value": "int64"})

        # Execute view builder
        result = registry.get("even_only")(table)
        df = result.execute()

        # Verify only even values
        assert list(df["value"]) == [2, 4, 6]

    def test_view_builder_with_mutation(self):
        """Test view builder with column mutation."""
        registry = ViewRegistry()

        @registry.register("add_double")
        def double_col(ir: Table) -> Table:
            return ir.mutate(doubled=ir.value * 2)

        # Create sample table
        table = ibis.memtable({"value": [1, 2, 3]}, schema={"value": "int64"})

        # Execute view builder
        result = registry.get("add_double")(table)
        df = result.execute()

        # Verify new column
        assert "doubled" in df.columns
        assert list(df["doubled"]) == [2, 4, 6]


class TestGlobalViewRegistry:
    """Tests for global 'views' registry singleton."""

    def test_global_registry_exists(self):
        """Test global 'views' registry is initialized."""
        assert isinstance(views, ViewRegistry)

    def test_chunks_view_registered(self):
        """Test 'chunks' view is registered."""
        assert views.has("chunks")

    def test_chunks_optimized_registered(self):
        """Test 'chunks_optimized' view is registered."""
        assert views.has("chunks_optimized")

    def test_messages_with_media_registered(self):
        """Test 'messages_with_media' view is registered."""
        assert views.has("messages_with_media")

    def test_messages_with_text_registered(self):
        """Test 'messages_with_text' view is registered."""
        assert views.has("messages_with_text")

    def test_hourly_aggregates_registered(self):
        """Test 'hourly_aggregates' view is registered."""
        assert views.has("hourly_aggregates")

    def test_daily_aggregates_registered(self):
        """Test 'daily_aggregates' view is registered."""
        assert views.has("daily_aggregates")

    def test_all_common_views_registered(self):
        """Test all expected common views are registered."""
        expected_views = {
            "chunks",
            "chunks_optimized",
            "messages_with_media",
            "messages_with_text",
            "hourly_aggregates",
            "daily_aggregates",
        }

        registered = set(views.list_views())
        assert expected_views.issubset(registered)


class TestCommonViews:
    """Tests for common pipeline views."""

    def test_chunks_view(self):
        """Test chunks view adds chunk_idx column."""
        from datetime import datetime
        import uuid

        # Create sample IR table with UUID strings
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        id3 = str(uuid.uuid4())
        t1 = str(uuid.uuid4())
        t2 = str(uuid.uuid4())

        data = {
            "event_id": [id1, id2, id3],
            "thread_id": [t1, t1, t2],
            "ts": [
                datetime(2025, 1, 1, 10, 0),
                datetime(2025, 1, 1, 11, 0),
                datetime(2025, 1, 1, 10, 30),
            ],
            "text": ["msg1", "msg2", "msg3"],
        }
        schema = {
            "event_id": "uuid",
            "thread_id": "uuid",
            "ts": "timestamp",
            "text": "string",
        }
        table = ibis.memtable(data, schema=schema)

        # Apply chunks view
        result = views.get("chunks")(table)
        df = result.execute()

        # Verify chunk_idx column added
        assert "chunk_idx" in df.columns

    def test_messages_with_media_view(self):
        """Test messages_with_media view filters correctly."""
        data = {
            "event_id": ["id1", "id2", "id3"],
            "text": ["msg1", "msg2", "msg3"],
            "media_url": ["http://example.com/img.jpg", None, "http://example.com/vid.mp4"],
        }
        schema = {"event_id": "string", "text": "string", "media_url": "string"}
        table = ibis.memtable(data, schema=schema)

        # Apply filter
        result = views.get("messages_with_media")(table)
        df = result.execute()

        # Should only have rows with media
        assert len(df) == 2
        assert all(df["media_url"].notnull())

    def test_messages_with_text_view(self):
        """Test messages_with_text view filters correctly."""
        data = {
            "event_id": ["id1", "id2", "id3", "id4"],
            "text": ["hello", None, "", "world"],
        }
        schema = {"event_id": "string", "text": "string"}
        table = ibis.memtable(data, schema=schema)

        # Apply filter
        result = views.get("messages_with_text")(table)
        df = result.execute()

        # Should only have rows with non-empty text
        assert len(df) == 2
        assert list(df["text"]) == ["hello", "world"]

    def test_hourly_aggregates_view(self):
        """Test hourly_aggregates view computes statistics."""
        from datetime import datetime
        import uuid

        # Create sample data spanning 2 hours
        # Use UUID strings for PyArrow compatibility
        data = {
            "ts": [
                datetime(2025, 1, 1, 10, 15),
                datetime(2025, 1, 1, 10, 30),
                datetime(2025, 1, 1, 11, 15),
                datetime(2025, 1, 1, 11, 30),
            ],
            "author_uuid": [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            ],
        }
        schema = {"ts": "timestamp", "author_uuid": "uuid"}
        table = ibis.memtable(data, schema=schema)

        # Apply aggregation
        result = views.get("hourly_aggregates")(table)
        df = result.execute()

        # Should have 2 rows (2 hours)
        assert len(df) == 2
        assert "hour" in df.columns
        assert "message_count" in df.columns
        assert "unique_authors" in df.columns

    def test_daily_aggregates_view(self):
        """Test daily_aggregates view computes statistics."""
        from datetime import datetime
        import uuid

        # Create sample data spanning 2 days
        # Use UUID strings for PyArrow compatibility
        data = {
            "ts": [
                datetime(2025, 1, 1, 10, 0),
                datetime(2025, 1, 1, 14, 0),
                datetime(2025, 1, 2, 10, 0),
            ],
            "author_uuid": [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            ],
        }
        schema = {"ts": "timestamp", "author_uuid": "uuid"}
        table = ibis.memtable(data, schema=schema)

        # Apply aggregation
        result = views.get("daily_aggregates")(table)
        df = result.execute()

        # Should have 2 rows (2 days)
        assert len(df) == 2
        assert "day" in df.columns
        assert "message_count" in df.columns


class TestViewBuilderType:
    """Tests for ViewBuilder type alias."""

    def test_view_builder_callable(self):
        """Test ViewBuilder is a callable type."""
        from collections.abc import Callable

        # ViewBuilder should be Callable[[Table], Table]
        def my_builder(ir: Table) -> Table:
            return ir.limit(1)

        # Should be compatible with ViewBuilder type
        assert isinstance(my_builder, Callable)

    def test_registry_accepts_view_builder(self):
        """Test registry accepts ViewBuilder callables."""
        registry = ViewRegistry()

        def valid_builder(ir: Table) -> Table:
            return ir

        # Should not raise
        registry.register_function("valid", valid_builder)
        assert registry.has("valid")
