import os
from pathlib import Path

import toml
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    gemini_api_key: str | None = None

def load_from_toml(config_path: Path) -> dict:
    """Loads settings from a TOML file."""
    if config_path.exists():
        return toml.load(config_path)
    return {}

def load_settings(cli_overrides: dict | None = None) -> Settings:
    """
    Loads settings with the correct precedence: CLI > ENV > TOML file.
    """
    if cli_overrides is None:
        cli_overrides = {}

    config_path = APP_DIR / "egregora.toml"
    toml_config = load_from_toml(config_path)

    # Load environment variables and defaults first.
    # We will merge the TOML values afterward so environment overrides win.
    base_settings = Settings()
    settings_data = base_settings.model_dump()

    model_config = getattr(Settings, "model_config", {}) or {}
    env_prefix = model_config.get("env_prefix", "")

    def env_var_candidates(field_name: str) -> list[str]:
        """Return possible environment variable names for the given field."""
        candidates = []
        base = f"{env_prefix}{field_name}" if env_prefix else field_name
        candidates.append(base)
        candidates.append(base.upper())
        candidates.append(base.lower())
        return candidates

    for key, value in toml_config.items():
        if cli_overrides and key in cli_overrides:
            continue

        env_set = any(os.getenv(candidate) is not None for candidate in env_var_candidates(key))
        if env_set:
            continue

        settings_data[key] = value

    if cli_overrides:
        settings_data.update(cli_overrides)

    return Settings(**settings_data)
