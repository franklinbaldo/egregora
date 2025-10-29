from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os
import toml
from typing import Optional

from egregora_v3.core.paths import APP_DIR

class Settings(BaseSettings):
    """
    Application settings, loaded from CLI, environment variables, and egregora.toml.
    """
    model_config = SettingsConfigDict(env_prefix='EGREGORA_')

    # Database path
    db_path: Path = APP_DIR / "egregora.db"

    # Embedding settings
    embedding_model: str = "models/embedding-001"
    embedding_dim: int = 768

    # Vector store settings
    vss_metric: str = "cosine"
    vss_nlist: int = 1000
    vss_nprobe: int = 10

    # API keys - loaded from environment or a secrets file
    gemini_api_key: Optional[str] = None

def load_from_toml(config_path: Path) -> dict:
    """Loads settings from a TOML file."""
    if config_path.exists():
        return toml.load(config_path)
    return {}

def load_settings(cli_overrides: Optional[dict] = None) -> Settings:
    """
    Loads settings with the correct precedence: CLI > ENV > TOML file.
    """
    if cli_overrides is None:
        cli_overrides = {}

    # Load from TOML file first
    config_path = APP_DIR / "egregora.toml"
    toml_config = load_from_toml(config_path)

    # Pydantic-settings will automatically load from environment variables.
    # We can then merge the configs, giving precedence to CLI overrides.

    # Start with TOML, then let Pydantic overwrite with ENV vars
    settings = Settings(**toml_config)

    # Finally, apply CLI overrides
    if cli_overrides:
        settings = Settings(**{**settings.dict(), **cli_overrides})

    return settings
