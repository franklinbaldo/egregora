import os
from pathlib import Path
from typing import Any

import yaml

from egregora_v3.core.config import EgregoraConfig


class ConfigLoader:
    """Loads and validates Egregora configuration."""

    def __init__(self, site_root: Path):
        self.site_root = site_root

    def load(self) -> EgregoraConfig:
        """Loads configuration from file and environment variables.

        Order of precedence:
        1. Environment variables (EGREGORA_SECTION__KEY)
        2. Config file (.egregora/config.yml)
        3. Defaults
        """
        config_data = self._load_from_file()
        self._apply_env_vars(config_data)

        # Inject site_root
        paths = config_data.get("paths")
        if paths is None:
            paths = {}
        elif not isinstance(paths, dict):
            msg = f"Configuration 'paths' must be a dictionary, got {type(paths).__name__}"
            raise ValueError(msg)

        paths["site_root"] = self.site_root
        config_data["paths"] = paths

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

    def _apply_env_vars(self, config_data: dict[str, Any]) -> None:
        """Overrides configuration with environment variables.

        Pattern: EGREGORA_SECTION__KEY (double underscore separator)
        Example: EGREGORA_MODELS__WRITER -> models.writer
        """
        prefix = "EGREGORA_"
        for env_key, env_val in os.environ.items():
            if not env_key.startswith(prefix):
                continue

            # Remove prefix
            key_path = env_key[len(prefix):].lower()

            # Split by double underscore to handle nested keys
            parts = key_path.split("__")

            # Navigate/Create nested dictionary structure
            current_level = config_data
            for i, part in enumerate(parts[:-1]):
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]
                if not isinstance(current_level, dict):
                     # If a key exists but isn't a dict (collision), skip env var
                     break
            else:
                # Set value at the leaf
                current_level[parts[-1]] = env_val
