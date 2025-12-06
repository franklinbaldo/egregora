from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from egregora_v3.core.config import EgregoraConfig, ModelSettings, PathsSettings, PipelineSettings


class ConfigLoader:
    """Loads and validates Egregora configuration.

    Handles YAML file loading and works with EgregoraConfig (BaseSettings)
    to automatically apply environment variable overrides.
    """

    def __init__(self, site_root: Path | None = None):
        """Initialize config loader.

        Args:
            site_root: Root directory of the site. If None, uses current working directory.

        """
        self.site_root = site_root if site_root is not None else Path.cwd()

    def load(self) -> EgregoraConfig:
        """Loads configuration with environment-variable precedence.

        Priority (highest to lowest):
        1. Environment variables (EGREGORA_SECTION__KEY)
        2. Config file (.egregora/config.yml relative to site_root)
        3. Defaults
        """
        file_config = self._normalized_config(self._load_from_file())
        merged = self._merge_config(
            base=EgregoraConfig().model_dump(mode="json"),
            override=file_config,
            env_override_paths=self._collect_env_override_paths(),
        )

        return EgregoraConfig.model_validate(merged)

    def _normalized_config(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """Ensure file configuration has a paths block and site_root set."""
        normalized = deepcopy(config_data) if config_data else {}

        paths = normalized.get("paths", {}) or {}
        if not isinstance(paths, dict):
            msg = f"Configuration 'paths' must be a dictionary, got {type(paths).__name__}"
            raise ValueError(msg)

        paths["site_root"] = self.site_root
        normalized["paths"] = paths
        return normalized

    def _collect_env_override_paths(self) -> set[tuple[str, ...]]:
        """Return the set of config paths defined via environment variables."""
        prefix = "EGREGORA_"
        env_paths: set[tuple[str, ...]] = set()

        for key in os.environ:
            if not key.startswith(prefix):
                continue
            parts = [part.lower() for part in key[len(prefix) :].split("__") if part]
            if parts:
                env_paths.add(tuple(parts))

        return env_paths

    def _merge_config(
        self,
        base: dict[str, Any],
        override: dict[str, Any],
        env_override_paths: set[tuple[str, ...]],
        current_path: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Merge override into base, skipping keys provided via env vars."""
        merged = deepcopy(base)

        for key, value in override.items():
            path = current_path + (str(key).lower(),)
            if path in env_override_paths:
                continue

            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_config(merged[key], value, env_override_paths, path)
            else:
                merged[key] = value

        return merged

    def _load_from_file(self) -> dict[str, Any]:
        """Loads configuration from .egregora/config.yml."""
        config_path = self.site_root / ".egregora" / "config.yml"
        if not config_path.exists():
            return {}

        try:
            with config_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if not isinstance(data, dict):
                    msg = (
                        "Configuration root must be a mapping (dictionary), "
                        f"got {type(data).__name__}"
                    )
                    raise ValueError(msg)
                return data
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}") from e
