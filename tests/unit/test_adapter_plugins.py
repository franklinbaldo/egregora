"""Tests for adapter plugin system.

Tests AdapterMeta, plugin loading, and adapter registry functionality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from egregora.sources.base import (
    AdapterMeta,
    InputMetadata,
    InputSource,
    InputSourceRegistry,
    input_registry,
)


class MockAdapter(InputSource):
    """Mock adapter for testing."""

    @property
    def source_type(self) -> str:
        return "mock"

    def adapter_meta(self) -> AdapterMeta:
        return {
            "name": "mock",
            "version": "1.0.0",
            "source": "Mock Platform",
            "doc_url": "https://example.com/mock",
            "ir_version": "v1",
        }

    def parse(self, source_path: Path, **kwargs: Any) -> tuple[Any, InputMetadata]:
        raise NotImplementedError

    def extract_media(self, source_path: Path, output_dir: Path, **kwargs: Any) -> dict[str, str]:
        return {}

    def supports_format(self, source_path: Path) -> bool:
        return source_path.name == "mock.txt"


class TestAdapterMeta:
    """Test AdapterMeta TypedDict."""

    def test_adapter_meta_structure(self):
        """Test AdapterMeta has required fields."""
        meta: AdapterMeta = {
            "name": "test",
            "version": "1.0.0",
            "source": "Test Platform",
            "doc_url": "https://example.com",
            "ir_version": "v1",
        }

        assert meta["name"] == "test"
        assert meta["version"] == "1.0.0"
        assert meta["source"] == "Test Platform"
        assert meta["doc_url"] == "https://example.com"
        assert meta["ir_version"] == "v1"


class TestInputSourceProtocol:
    """Test InputSource protocol compliance."""

    def test_mock_adapter_implements_protocol(self):
        """Test mock adapter implements all required methods."""
        adapter = MockAdapter()

        # Check required methods exist
        assert hasattr(adapter, "source_type")
        assert hasattr(adapter, "adapter_meta")
        assert hasattr(adapter, "parse")
        assert hasattr(adapter, "extract_media")
        assert hasattr(adapter, "supports_format")

    def test_adapter_meta_returns_correct_structure(self):
        """Test adapter_meta returns AdapterMeta dict."""
        adapter = MockAdapter()
        meta = adapter.adapter_meta()

        assert isinstance(meta, dict)
        assert "name" in meta
        assert "version" in meta
        assert "source" in meta
        assert "doc_url" in meta
        assert "ir_version" in meta

    def test_adapter_source_type_property(self):
        """Test source_type property."""
        adapter = MockAdapter()
        assert adapter.source_type == "mock"


class TestInputSourceRegistry:
    """Test InputSourceRegistry functionality."""

    def test_registry_initialization(self):
        """Test registry initializes correctly."""
        registry = InputSourceRegistry()

        assert isinstance(registry._sources, dict)
        assert registry._plugins_loaded is False

    def test_register_adapter(self):
        """Test registering an adapter."""
        registry = InputSourceRegistry()
        registry.register(MockAdapter)

        assert "mock" in registry._sources
        assert registry._sources["mock"] == MockAdapter

    def test_get_source_registered(self):
        """Test getting a registered adapter."""
        registry = InputSourceRegistry()
        registry.register(MockAdapter)

        adapter = registry.get_source("mock")

        assert isinstance(adapter, MockAdapter)
        assert adapter.source_type == "mock"

    def test_get_source_not_registered(self):
        """Test getting non-existent adapter raises KeyError."""
        registry = InputSourceRegistry()

        with pytest.raises(KeyError, match="not found"):
            registry.get_source("nonexistent")

    def test_list_sources_empty(self):
        """Test listing sources when registry is empty."""
        registry = InputSourceRegistry()

        sources = registry.list_sources()

        assert isinstance(sources, list)
        # May be empty or contain plugins depending on environment

    def test_list_sources_with_registered(self):
        """Test listing sources after registration."""
        registry = InputSourceRegistry()
        registry.register(MockAdapter)

        sources = registry.list_sources()

        assert "mock" in sources

    def test_detect_source_matching(self):
        """Test auto-detecting matching adapter."""
        registry = InputSourceRegistry()
        registry.register(MockAdapter)

        # Create matching path
        source_path = Path("mock.txt")

        adapter = registry.detect_source(source_path)

        assert adapter is not None
        assert isinstance(adapter, MockAdapter)

    def test_detect_source_no_match(self):
        """Test auto-detecting when no adapter matches."""
        registry = InputSourceRegistry()
        registry.register(MockAdapter)

        # Create non-matching path
        source_path = Path("other.txt")

        adapter = registry.detect_source(source_path)

        assert adapter is None

    def test_get_adapter_metadata(self):
        """Test getting metadata for all adapters."""
        registry = InputSourceRegistry()
        registry.register(MockAdapter)

        metadata = registry.get_adapter_metadata()

        assert isinstance(metadata, list)
        assert len(metadata) >= 1

        # Check mock adapter metadata is present
        mock_meta = [m for m in metadata if m["name"] == "mock"]
        assert len(mock_meta) == 1
        assert mock_meta[0]["version"] == "1.0.0"
        assert mock_meta[0]["ir_version"] == "v1"

    def test_lazy_plugin_loading(self):
        """Test plugins are loaded lazily."""
        registry = InputSourceRegistry()

        # Plugins not loaded initially
        assert registry._plugins_loaded is False

        # Accessing registry triggers plugin loading
        _ = registry.list_sources()

        # Now plugins should be loaded
        assert registry._plugins_loaded is True

    def test_plugin_loading_idempotent(self):
        """Test plugin loading only happens once."""
        registry = InputSourceRegistry()

        # Load plugins multiple times
        registry._load_plugins()
        registry._load_plugins()
        registry._load_plugins()

        # Should only load once
        assert registry._plugins_loaded is True


class TestBuiltInAdapters:
    """Test built-in adapters have adapter_meta."""

    def test_whatsapp_adapter_has_metadata(self):
        """Test WhatsApp adapter implements adapter_meta."""
        from egregora.sources.whatsapp.input import WhatsAppInputSource

        adapter = WhatsAppInputSource()
        meta = adapter.adapter_meta()

        assert meta["name"] == "whatsapp"
        assert meta["ir_version"] == "v1"
        assert "version" in meta
        assert "doc_url" in meta

    def test_slack_adapter_has_metadata(self):
        """Test Slack adapter implements adapter_meta."""
        from egregora.ingestion.slack_input import SlackInputSource

        adapter = SlackInputSource()
        meta = adapter.adapter_meta()

        assert meta["name"] == "slack"
        assert meta["ir_version"] == "v1"
        assert "version" in meta
        assert "doc_url" in meta


class TestGlobalRegistry:
    """Test global input_registry instance."""

    def test_global_registry_exists(self):
        """Test global registry is accessible."""
        assert input_registry is not None
        assert isinstance(input_registry, InputSourceRegistry)

    def test_global_registry_has_whatsapp(self):
        """Test global registry includes WhatsApp adapter."""
        # This will trigger plugin loading
        sources = input_registry.list_sources()

        assert "whatsapp" in sources

    def test_global_registry_metadata(self):
        """Test getting metadata from global registry."""
        metadata = input_registry.get_adapter_metadata()

        assert isinstance(metadata, list)
        assert len(metadata) > 0

        # Should have at least WhatsApp
        whatsapp_meta = [m for m in metadata if m["name"] == "whatsapp"]
        assert len(whatsapp_meta) == 1
