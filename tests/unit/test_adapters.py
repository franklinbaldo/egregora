"""Tests for source adapters (WhatsApp, Slack placeholder, etc.)."""

import tempfile
from pathlib import Path

import pytest

from egregora.input_adapters import ADAPTER_REGISTRY, get_adapter
from egregora.input_adapters.slack import SLACK_ADAPTER_PLACEHOLDER
from egregora.input_adapters.whatsapp import WhatsAppAdapter


class TestAdapterRegistry:
    """Test adapter registry functionality."""

    def test_registry_contains_whatsapp_adapter(self):
        """Registry should contain WhatsApp adapter."""
        assert "whatsapp" in ADAPTER_REGISTRY
        assert ADAPTER_REGISTRY["whatsapp"] == WhatsAppAdapter

    def test_get_adapter_returns_whatsapp_instance(self):
        """get_adapter should return WhatsApp adapter instance."""
        adapter = get_adapter("whatsapp")
        assert isinstance(adapter, WhatsAppAdapter)

    def test_slack_adapter_not_registered(self):
        """Slack should not be registered as a built-in adapter."""
        assert "slack" not in ADAPTER_REGISTRY

    def test_get_adapter_raises_for_unknown_source(self):
        """get_adapter should raise KeyError for unknown source."""
        with pytest.raises(KeyError, match="Unknown source"):
            get_adapter("discord")

    def test_get_adapter_raises_for_disabled_slack(self):
        """Slack adapter should not be available via get_adapter."""
        with pytest.raises(KeyError, match="Unknown source: 'slack'"):
            get_adapter("slack")


class TestWhatsAppAdapter:
    """Test WhatsApp adapter functionality."""

    def test_source_name(self):
        """WhatsApp adapter should have correct source name."""
        adapter = WhatsAppAdapter()
        assert adapter.source_name == "WhatsApp"

    def test_source_identifier(self):
        """WhatsApp adapter should have correct identifier."""
        adapter = WhatsAppAdapter()
        assert adapter.source_identifier == "whatsapp"

    def test_parse_with_nonexistent_file_raises(self):
        """Parse should raise FileNotFoundError for missing file."""
        adapter = WhatsAppAdapter()

        with pytest.raises(FileNotFoundError):
            adapter.parse(Path("/nonexistent/file.zip"))

    def test_parse_with_non_zip_file_raises(self):
        """Parse should raise ValueError for non-ZIP files."""
        adapter = WhatsAppAdapter()

        # Create a temporary non-ZIP file

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with pytest.raises(ValueError, match="Expected a ZIP file"):
                adapter.parse(tmp_path)
        finally:
            tmp_path.unlink()

    def test_extract_media_returns_empty_dict(self):
        """extract_media should return empty dict (media handled in pipeline)."""
        adapter = WhatsAppAdapter()

        # Mock path (doesn't need to exist for this test)
        result = adapter.extract_media(Path("/mock/path.zip"), Path("/output"))

        assert result == {}

    def test_get_metadata_with_nonexistent_file_raises(self):
        """get_metadata should raise FileNotFoundError for missing file."""
        adapter = WhatsAppAdapter()

        with pytest.raises(FileNotFoundError):
            adapter.get_metadata(Path("/nonexistent/file.zip"))

    @pytest.mark.parametrize(
        "method_name",
        ["parse", "extract_media", "get_metadata"],
    )
    def test_adapter_methods_exist(self, method_name):
        """Adapter should implement all required methods."""
        adapter = WhatsAppAdapter()
        assert hasattr(adapter, method_name)
        assert callable(getattr(adapter, method_name))


class TestSlackPlaceholder:
    """Test Slack placeholder messaging."""

    def test_placeholder_mentions_disabled_status(self):
        """Placeholder should clearly indicate Slack is disabled."""
        placeholder = SLACK_ADAPTER_PLACEHOLDER.lower()
        assert "disabled" in placeholder or "not registered" in placeholder


class TestAdapterContract:
    """Test that all adapters follow the InputAdapter contract."""

    @pytest.mark.parametrize("source_id", list(ADAPTER_REGISTRY.keys()))
    def test_adapter_has_source_name_property(self, source_id):
        """All adapters should have source_name property."""
        adapter = get_adapter(source_id)
        assert isinstance(adapter.source_name, str)
        assert len(adapter.source_name) > 0

    @pytest.mark.parametrize("source_id", list(ADAPTER_REGISTRY.keys()))
    def test_adapter_has_source_identifier_property(self, source_id):
        """All adapters should have source_identifier property."""
        adapter = get_adapter(source_id)
        assert isinstance(adapter.source_identifier, str)
        assert adapter.source_identifier == source_id

    @pytest.mark.parametrize("source_id", list(ADAPTER_REGISTRY.keys()))
    def test_adapter_has_parse_method(self, source_id):
        """All adapters should implement parse method."""
        adapter = get_adapter(source_id)
        assert hasattr(adapter, "parse")
        assert callable(adapter.parse)

    @pytest.mark.parametrize("source_id", list(ADAPTER_REGISTRY.keys()))
    def test_adapter_has_extract_media_method(self, source_id):
        """All adapters should implement extract_media method."""
        adapter = get_adapter(source_id)
        assert hasattr(adapter, "extract_media")
        assert callable(adapter.extract_media)

    @pytest.mark.parametrize("source_id", list(ADAPTER_REGISTRY.keys()))
    def test_adapter_has_get_metadata_method(self, source_id):
        """All adapters should implement get_metadata method."""
        adapter = get_adapter(source_id)
        assert hasattr(adapter, "get_metadata")
        assert callable(adapter.get_metadata)

    @pytest.mark.parametrize("source_id", list(ADAPTER_REGISTRY.keys()))
    def test_adapter_repr_is_meaningful(self, source_id):
        """All adapters should have meaningful string representation."""
        adapter = get_adapter(source_id)
        repr_str = repr(adapter)

        assert source_id in repr_str.lower()
        assert "Adapter" in repr_str
