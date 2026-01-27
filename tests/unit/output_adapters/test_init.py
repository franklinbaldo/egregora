from unittest.mock import MagicMock, patch

from egregora.config.settings import EgregoraConfig
from egregora.output_sinks import create_and_initialize_adapter


def test_create_and_initialize_adapter_detects_mkdocs(tmp_path):
    """Test that adapter is created and initialized."""
    output_dir = tmp_path / "site"
    output_dir.mkdir()
    (output_dir / "mkdocs.yml").touch()

    config = MagicMock(spec=EgregoraConfig)

    # Mock MkDocsPaths to return our output_dir as site_root
    with (
        patch("egregora.output_sinks.MkDocsPaths") as mock_paths_cls,
        patch("egregora.output_sinks.create_output_sink") as mock_create_sink,
        patch("egregora.output_sinks.create_default_output_registry") as mock_create_registry,
    ):
        mock_paths_instance = MagicMock()
        mock_paths_instance.site_root = output_dir
        mock_paths_cls.return_value = mock_paths_instance

        mock_adapter = MagicMock()
        mock_create_sink.return_value = mock_adapter

        # Registry detect_format returns None to trigger create_output_sink
        mock_registry = MagicMock()
        mock_registry.detect_format.return_value = None
        mock_create_registry.return_value = mock_registry

        adapter = create_and_initialize_adapter(config, output_dir)

        assert adapter is mock_adapter
        mock_create_sink.assert_called_once()
        mock_adapter.initialize.assert_called_once()


def test_create_and_initialize_adapter_uses_existing_registry(tmp_path):
    """Test that adapter uses provided registry."""
    output_dir = tmp_path / "site"
    config = MagicMock(spec=EgregoraConfig)
    registry = MagicMock()
    mock_adapter = MagicMock()
    registry.detect_format.return_value = mock_adapter

    with patch("egregora.output_sinks.MkDocsPaths") as mock_paths_cls:
        mock_paths_instance = MagicMock()
        mock_paths_instance.site_root = output_dir
        mock_paths_cls.return_value = mock_paths_instance

        adapter = create_and_initialize_adapter(config, output_dir, registry=registry)

        assert adapter is mock_adapter
        registry.detect_format.assert_called_once()
        mock_adapter.initialize.assert_called_once()
