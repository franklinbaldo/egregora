"""Tests for database view registry (ViewBuilder pattern)."""

import ibis
import pytest

from egregora.database.views import ViewBuilder, ViewRegistry, views


@pytest.fixture
def registry():
    """Create fresh ViewRegistry for testing."""
    return ViewRegistry()


@pytest.fixture
def sample_table():
    """Create sample Ibis table for testing."""
    data = {
        "id": [1, 2, 3, 4, 5],
        "author": ["alice", "bob", "alice", "charlie", "bob"],
        "message": ["Hello", "Hi", "How are you?", "Good morning", "Nice day"],
        "timestamp": [
            "2025-01-01 10:00",
            "2025-01-01 11:00",
            "2025-01-01 12:00",
            "2025-01-02 09:00",
            "2025-01-02 10:00",
        ],
    }
    return ibis.memtable(data)


class TestViewRegistry:
    """Tests for ViewRegistry class."""

    def test_init(self, registry: ViewRegistry):
        """ViewRegistry initializes with empty views dict."""
        assert registry.list_views() == []

    def test_register_decorator(self, registry: ViewRegistry, sample_table: ibis.Table):
        """@register decorator registers view builder."""

        @registry.register("test_view")
        def test_builder(ir: ibis.Table) -> ibis.Table:
            return ir.limit(2)

        assert registry.has("test_view")
        builder = registry.get("test_view")
        result = builder(sample_table)
        assert result.count().execute() == 2

    def test_register_function(self, registry: ViewRegistry, sample_table: ibis.Table):
        """register_function() registers builder without decorator."""

        def test_builder(ir: ibis.Table) -> ibis.Table:
            return ir.filter(ir.author == "alice")

        registry.register_function("alice_messages", test_builder)

        assert registry.has("alice_messages")
        builder = registry.get("alice_messages")
        result = builder(sample_table)
        assert result.count().execute() == 2  # alice has 2 messages

    def test_register_duplicate_raises(self, registry: ViewRegistry):
        """Registering duplicate view name raises ValueError."""

        @registry.register("duplicate")
        def first(ir: ibis.Table) -> ibis.Table:
            return ir

        with pytest.raises(ValueError, match="already registered"):

            @registry.register("duplicate")
            def second(ir: ibis.Table) -> ibis.Table:
                return ir

    def test_register_function_duplicate_raises(self, registry: ViewRegistry):
        """register_function() raises ValueError for duplicates."""

        def builder(ir: ibis.Table) -> ibis.Table:
            return ir

        registry.register_function("test", builder)

        with pytest.raises(ValueError, match="already registered"):
            registry.register_function("test", builder)

    def test_get(self, registry: ViewRegistry):
        """get() returns registered builder."""

        def builder(ir: ibis.Table) -> ibis.Table:
            return ir

        registry.register_function("test", builder)
        retrieved = registry.get("test")

        assert retrieved is builder

    def test_get_nonexistent_raises(self, registry: ViewRegistry):
        """get() raises KeyError for unregistered view."""
        with pytest.raises(KeyError, match="View not found"):
            registry.get("nonexistent")

    def test_has(self, registry: ViewRegistry):
        """has() returns True for registered views, False otherwise."""

        @registry.register("exists")
        def builder(ir: ibis.Table) -> ibis.Table:
            return ir

        assert registry.has("exists") is True
        assert registry.has("does_not_exist") is False

    def test_list_views(self, registry: ViewRegistry):
        """list_views() returns sorted list of view names."""

        @registry.register("view_c")
        def c(ir: ibis.Table) -> ibis.Table:
            return ir

        @registry.register("view_a")
        def a(ir: ibis.Table) -> ibis.Table:
            return ir

        @registry.register("view_b")
        def b(ir: ibis.Table) -> ibis.Table:
            return ir

        views_list = registry.list_views()
        assert views_list == ["view_a", "view_b", "view_c"]  # sorted

    def test_unregister(self, registry: ViewRegistry):
        """unregister() removes view from registry."""

        @registry.register("temp")
        def builder(ir: ibis.Table) -> ibis.Table:
            return ir

        assert registry.has("temp")
        registry.unregister("temp")
        assert not registry.has("temp")

    def test_unregister_nonexistent_raises(self, registry: ViewRegistry):
        """unregister() raises KeyError for nonexistent view."""
        with pytest.raises(KeyError, match="View not found"):
            registry.unregister("nonexistent")

    def test_clear(self, registry: ViewRegistry):
        """clear() removes all views."""

        @registry.register("view1")
        def v1(ir: ibis.Table) -> ibis.Table:
            return ir

        @registry.register("view2")
        def v2(ir: ibis.Table) -> ibis.Table:
            return ir

        assert len(registry.list_views()) == 2
        registry.clear()
        assert len(registry.list_views()) == 0


class TestViewBuilders:
    """Tests for actual view builder functions."""

    def test_filter_view(self, registry: ViewRegistry, sample_table: ibis.Table):
        """View builder can filter rows."""

        @registry.register("bob_only")
        def bob_messages(ir: ibis.Table) -> ibis.Table:
            return ir.filter(ir.author == "bob")

        builder = registry.get("bob_only")
        result = builder(sample_table).execute()

        assert len(result) == 2
        assert all(result["author"] == "bob")

    def test_mutate_view(self, registry: ViewRegistry, sample_table: ibis.Table):
        """View builder can add computed columns."""

        @registry.register("with_length")
        def add_length(ir: ibis.Table) -> ibis.Table:
            return ir.mutate(msg_length=ir.message.length())

        builder = registry.get("with_length")
        result = builder(sample_table).execute()

        assert "msg_length" in result.columns
        assert result["msg_length"].iloc[0] == len("Hello")

    def test_aggregate_view(self, registry: ViewRegistry, sample_table: ibis.Table):
        """View builder can perform aggregations."""

        @registry.register("author_counts")
        def count_by_author(ir: ibis.Table) -> ibis.Table:
            return ir.group_by("author").aggregate(count=ir.count())

        builder = registry.get("author_counts")
        result = builder(sample_table).execute()

        assert len(result) == 3  # 3 unique authors
        alice_count = result[result["author"] == "alice"]["count"].iloc[0]
        assert alice_count == 2

    def test_chained_views(self, registry: ViewRegistry, sample_table: ibis.Table):
        """Views can be chained together."""

        @registry.register("filtered")
        def filter_step(ir: ibis.Table) -> ibis.Table:
            return ir.filter(ir.author.isin(["alice", "bob"]))

        @registry.register("with_length")
        def mutate_step(ir: ibis.Table) -> ibis.Table:
            return ir.mutate(msg_length=ir.message.length())

        # Chain: filter then mutate
        filtered = registry.get("filtered")
        with_length = registry.get("with_length")

        result = with_length(filtered(sample_table)).execute()

        assert len(result) == 4  # alice(2) + bob(2), charlie filtered out
        assert "msg_length" in result.columns


class TestGlobalViewsRegistry:
    """Tests for the global views registry instance."""

    def test_global_registry_exists(self):
        """Global 'views' registry is available for import."""
        assert isinstance(views, ViewRegistry)

    def test_global_registry_can_register(self, sample_table: ibis.Table):
        """Can register views on global registry."""
        # Clean up first (in case test ran before)
        if views.has("test_global"):
            views.unregister("test_global")

        @views.register("test_global")
        def test(ir: ibis.Table) -> ibis.Table:
            return ir.limit(1)

        try:
            assert views.has("test_global")
            builder = views.get("test_global")
            result = builder(sample_table)
            assert result.count().execute() == 1
        finally:
            # Clean up
            views.unregister("test_global")
