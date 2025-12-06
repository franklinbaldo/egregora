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
        """Loads configuration from file and environment variables.

        Looks for .egregora/config.yml relative to site_root (or CWD if not specified).
        Environment variables automatically override file values via Pydantic Settings.

        Priority (highest to lowest):
        1. Environment variables (EGREGORA_SECTION__KEY)
        2. Config file (.egregora/config.yml relative to site_root)
        3. Defaults

        Returns:
            EgregoraConfig: Fully loaded and validated configuration.

        Examples:
            # Default: use current working directory
            loader = ConfigLoader()
            config = loader.load()  # Looks for .egregora/config.yml in CWD

            # Explicit: use specific directory (e.g., from CLI --site-root)
            loader = ConfigLoader(Path("/path/to/site"))
            config = loader.load()  # Looks for .egregora/config.yml in /path/to/site
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

        # Create config from environment variables and defaults FIRST
        # This ensures env vars have highest priority
        config = EgregoraConfig()

        # Now merge file data for fields that weren't set by environment variables
        # We do this by comparing each field value to its default
        if "models" in config_data:
            file_models = config_data["models"]
            defaults = ModelSettings()
            # Only update if current value is default AND file has a value
            for key, value in file_models.items():
                current = getattr(config.models, key, None)
                default = getattr(defaults, key, None)
                if current == default and value is not None:
                    setattr(config.models, key, value)

        if "pipeline" in config_data:
            file_pipeline = config_data["pipeline"]
            defaults = PipelineSettings()
            for key, value in file_pipeline.items():
                current = getattr(config.pipeline, key, None)
                default = getattr(defaults, key, None)
                if current == default and value is not None:
                    setattr(config.pipeline, key, value)

        # Always update paths.site_root (this is injected and always set)
        config.paths.site_root = paths["site_root"]

        # Update other path fields only if not set by env vars
        if "paths" in config_data:
            file_paths = config_data["paths"]
            defaults = PathsSettings()
            for key, value in file_paths.items():
                if key == "site_root":
                    continue  # Already set above
                current = getattr(config.paths, key, None)
                default = getattr(defaults, key, None)
                if current == default and value is not None:
                    setattr(config.paths, key, Path(value))

        return config

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
