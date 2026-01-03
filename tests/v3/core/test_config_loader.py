from egregora_v3.core.config import EgregoraConfig
from egregora_v3.core.loader import ConfigLoader

def test_config_loader_returns_config():
    """Test that ConfigLoader loads EgregoraConfig."""
    config = ConfigLoader.load()
    assert isinstance(config, EgregoraConfig)

def test_egregora_config_load_delegates_to_loader():
    """Test that EgregoraConfig.load() works and returns a config instance."""
    config = EgregoraConfig.load()
    assert isinstance(config, EgregoraConfig)
    # Check default value
    assert config.models.writer == "google-gla:gemini-2.0-flash"
