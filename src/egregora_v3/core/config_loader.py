from pathlib import Path
from typing import Any

import yaml

from egregora_v3.core.config import EgregoraConfig


class ConfigLoader:
    """Loads and validates Egregora configuration.

    Handles YAML file loading and works with EgregoraConfig (BaseSettings)
    to automatically apply environment variable overrides.
    """

    def __init__(self, site_root: Path):
        self.site_root = site_root

    def load(self) -> EgregoraConfig:
        """Loads configuration from file and environment variables.

        Environment variables automatically override file values via Pydantic Settings.
        Priority (highest to lowest):
        1. Environment variables (EGREGORA_SECTION__KEY)
        2. Config file (.egregora/config.yml)
        3. Defaults
        """
        config_data = self._load_from_file()

        # Inject site_root
        paths = config_data.get("paths")
        if paths is None:
            paths = {}
        elif not isinstance(paths, dict):
            msg = f"Configuration 'paths' must be a dictionary, got {type(paths).__name__}"
            raise ValueError(msg)

        paths["site_root"] = self.site_root
        config_data["paths"] = paths

        # EgregoraConfig (BaseSettings) automatically handles env var overrides
        return EgregoraConfig(**config_data)

    def _load_from_file(self) -> dict[str, Any]:
        """Loads configuration from .egregora/config.yml."""
        config_path = self.site_root / ".egregora" / "config.yml"
        if not config_path.exists():
            return {}

        try:
            with config_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if not isinstance(data, dict):
                    return {}
                return data
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}") from e
