"""Centralized Gemini model configuration for all agents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import yaml

logger = logging.getLogger(__name__)

# Default models for different tasks
DEFAULT_WRITER_MODEL = "models/gemini-flash-latest"
DEFAULT_ENRICHER_MODEL = "models/gemini-flash-latest"
DEFAULT_ENRICHER_VISION_MODEL = "models/gemini-flash-latest"
DEFAULT_RANKING_MODEL = "models/gemini-flash-latest"
DEFAULT_EDITOR_MODEL = "models/gemini-flash-latest"
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"

ModelType = Literal["writer", "enricher", "enricher_vision", "ranking", "editor", "embedding"]


class ModelConfig:
    """Centralized model configuration with fallback hierarchy."""

    def __init__(
        self,
        cli_model: str | None = None,
        site_config: dict | None = None,
    ):
        """
        Initialize model config with CLI override and site config.

        Args:
            cli_model: Model specified via CLI flag (highest priority)
            site_config: Configuration from mkdocs.yml extra.egregora section
        """
        self.cli_model = cli_model
        self.site_config = site_config or {}

    def get_model(self, model_type: ModelType) -> str:
        """
        Get model name for a specific task with fallback hierarchy.

        Priority:
        1. CLI flag (--model)
        2. mkdocs.yml extra.egregora.models.{type}
        3. mkdocs.yml extra.egregora.model (global override)
        4. Default for task type

        Args:
            model_type: Type of model to retrieve

        Returns:
            Model name to use
        """
        # 1. CLI flag (highest priority)
        if self.cli_model:
            logger.debug(f"Using CLI model for {model_type}: {self.cli_model}")
            return self.cli_model

        # 2. Specific model for this task in site config
        models_config = self.site_config.get("models", {})
        if model_type in models_config:
            model = models_config[model_type]
            logger.debug(f"Using site config model for {model_type}: {model}")
            return model

        # 3. Global model override in site config
        if "model" in self.site_config:
            model = self.site_config["model"]
            logger.debug(f"Using global site config model for {model_type}: {model}")
            return model

        # 4. Default for task type
        defaults = {
            "writer": DEFAULT_WRITER_MODEL,
            "enricher": DEFAULT_ENRICHER_MODEL,
            "enricher_vision": DEFAULT_ENRICHER_VISION_MODEL,
            "ranking": DEFAULT_RANKING_MODEL,
            "editor": DEFAULT_EDITOR_MODEL,
            "embedding": DEFAULT_EMBEDDING_MODEL,
        }
        model = defaults[model_type]
        logger.debug(f"Using default model for {model_type}: {model}")
        return model


def load_site_config(output_dir: Path) -> dict:
    """
    Load egregora configuration from mkdocs.yml if it exists.

    Args:
        output_dir: Output directory (will look for mkdocs.yml in parent/root)

    Returns:
        Dict with egregora config from extra.egregora section
    """
    # Try to find mkdocs.yml in parent directory (site root)
    mkdocs_path = output_dir.parent / "mkdocs.yml"

    # If not found, try in output_dir itself
    if not mkdocs_path.exists():
        mkdocs_path = output_dir / "mkdocs.yml"

    if not mkdocs_path.exists():
        logger.debug("No mkdocs.yml found, using default config")
        return {}

    try:
        config = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8"))
        egregora_config = config.get("extra", {}).get("egregora", {})
        logger.debug(f"Loaded site config from {mkdocs_path}")
        return egregora_config
    except Exception as e:
        logger.warning(f"Could not load site config from {mkdocs_path}: {e}")
        return {}
