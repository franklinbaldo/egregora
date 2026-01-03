from __future__ import annotations

from pathlib import Path

from egregora_v3.core.config import EgregoraConfig


class ConfigLoader:
    """Loads configuration for Egregora V3."""

    @staticmethod
    def load(site_root: Path | None = None) -> EgregoraConfig:
        """Loads the configuration."""
        if site_root is None:
            site_root = Path.cwd()

        # For now, we rely on the Pydantic BaseSettings behavior which will look for
        # the toml_file defined in EgregoraConfig.model_config in the current working directory.
        # If we need to support finding the config file in parent directories, we would
        # implement that search logic here and perhaps change the working directory
        # or instantiate EgregoraConfig with explicit source overrides.

        return EgregoraConfig()
