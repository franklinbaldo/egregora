"""Tests for adapter registry and plugin discovery.

Tests cover:
- AdapterRegistry initialization
- Built-in adapter loading (WhatsApp, Slack)
- Plugin discovery via entry points
- IR version validation
- Adapter lookup and listing
- Error handling for invalid adapters
"""

from __future__ import annotations

import pytest

from egregora.adapters.registry import AdapterRegistry, get_global_registry


class TestAdapterRegistry:
    """Tests for AdapterRegistry class."""

    def test_registry_initialization(self) -> None:
        """Test that registry initializes with built-in adapters."""
        registry = AdapterRegistry()

        # Should load WhatsApp and Slack adapters
        assert len(registry) >= 2
        assert "whatsapp" in registry
        assert "slack" in registry

    def test_get_whatsapp_adapter(self) -> None:
        """Test retrieving WhatsApp adapter."""
        registry = AdapterRegistry()
        adapter = registry.get("whatsapp")

        assert adapter.source_identifier == "whatsapp"
        assert adapter.source_name == "WhatsApp"

        # Verify adapter_meta()
        meta = adapter.adapter_meta()
        assert meta["name"] == "WhatsApp"
        assert meta["version"] == "1.0.0"
        assert meta["source"] == "whatsapp"
        assert meta["ir_version"] == "v1"
        assert "github.com" in meta["doc_url"]

    def test_get_slack_adapter(self) -> None:
        """Test retrieving Slack adapter (stub)."""
        registry = AdapterRegistry()
        adapter = registry.get("slack")

        assert adapter.source_identifier == "slack"
        assert adapter.source_name == "Slack"

        # Verify adapter_meta()
        meta = adapter.adapter_meta()
        assert meta["name"] == "Slack"
        assert meta["version"] == "0.1.0"
        assert meta["source"] == "slack"
        assert meta["ir_version"] == "v1"

    def test_get_unknown_adapter_raises_keyerror(self) -> None:
        """Test that getting unknown adapter raises KeyError."""
        registry = AdapterRegistry()

        with pytest.raises(KeyError, match="Unknown source: 'unknown'"):
            registry.get("unknown")

    def test_list_adapters(self) -> None:
        """Test listing all adapters."""
        registry = AdapterRegistry()
        adapters = registry.list_adapters()

        # Should be a list of AdapterMeta dicts
        assert isinstance(adapters, list)
        assert len(adapters) >= 2

        # Verify structure
        for meta in adapters:
            assert "name" in meta
            assert "version" in meta
            assert "source" in meta
            assert "doc_url" in meta
            assert "ir_version" in meta

        # Check specific adapters
        sources = {meta["source"] for meta in adapters}
        assert "whatsapp" in sources
        assert "slack" in sources

    def test_contains_operator(self) -> None:
        """Test __contains__ operator."""
        registry = AdapterRegistry()

        assert "whatsapp" in registry
        assert "slack" in registry
        assert "unknown" not in registry

    def test_len_operator(self) -> None:
        """Test __len__ operator."""
        registry = AdapterRegistry()
        assert len(registry) >= 2

    def test_repr(self) -> None:
        """Test __repr__ string representation."""
        registry = AdapterRegistry()
        repr_str = repr(registry)

        assert "AdapterRegistry" in repr_str
        assert "adapters=" in repr_str
        assert "whatsapp" in repr_str
        assert "slack" in repr_str


class TestGlobalRegistry:
    """Tests for global registry singleton."""

    def test_get_global_registry_returns_singleton(self) -> None:
        """Test that get_global_registry returns same instance."""
        registry1 = get_global_registry()
        registry2 = get_global_registry()

        assert registry1 is registry2

    def test_global_registry_has_builtin_adapters(self) -> None:
        """Test that global registry loads built-in adapters."""
        registry = get_global_registry()

        assert "whatsapp" in registry
        assert "slack" in registry


class TestAdapterMeta:
    """Tests for AdapterMeta TypedDict."""

    def test_adapter_meta_structure(self) -> None:
        """Test that AdapterMeta has correct structure."""
        registry = AdapterRegistry()
        adapter = registry.get("whatsapp")
        meta = adapter.adapter_meta()

        # Verify all required fields
        assert isinstance(meta["name"], str)
        assert isinstance(meta["version"], str)
        assert isinstance(meta["source"], str)
        assert isinstance(meta["doc_url"], str)
        assert isinstance(meta["ir_version"], str)

    def test_adapter_meta_ir_version_v1(self) -> None:
        """Test that all adapters support IR v1."""
        registry = AdapterRegistry()

        for meta in registry.list_adapters():
            assert meta["ir_version"] == "v1", f"Adapter {meta['name']} should support IR v1"


class TestAdapterProtocol:
    """Tests for adapter protocol compliance."""

    def test_whatsapp_adapter_implements_protocol(self) -> None:
        """Test that WhatsApp adapter implements full protocol."""
        registry = AdapterRegistry()
        adapter = registry.get("whatsapp")

        # Required properties
        assert hasattr(adapter, "source_name")
        assert hasattr(adapter, "source_identifier")

        # Required methods
        assert hasattr(adapter, "adapter_meta")
        assert hasattr(adapter, "parse")

        # Optional methods
        assert hasattr(adapter, "deliver_media")
        assert hasattr(adapter, "get_metadata")

    def test_slack_adapter_implements_protocol(self) -> None:
        """Test that Slack adapter implements full protocol."""
        registry = AdapterRegistry()
        adapter = registry.get("slack")

        # Required properties
        assert hasattr(adapter, "source_name")
        assert hasattr(adapter, "source_identifier")

        # Required methods
        assert hasattr(adapter, "adapter_meta")
        assert hasattr(adapter, "parse")

        # Optional methods
        assert hasattr(adapter, "extract_media")
        assert hasattr(adapter, "get_metadata")


class TestLegacyCompatibility:
    """Tests for backward compatibility with old get_adapter() function."""

    def test_get_adapter_function_still_works(self) -> None:
        """Test that legacy get_adapter() function still works."""
        from egregora.adapters import get_adapter

        adapter = get_adapter("whatsapp")
        assert adapter.source_identifier == "whatsapp"

    def test_get_adapter_raises_on_unknown(self) -> None:
        """Test that legacy get_adapter() raises KeyError."""
        from egregora.adapters import get_adapter

        with pytest.raises(KeyError, match="Unknown source"):
            get_adapter("unknown")
