"""Centralized Gemini model configuration for all agents."""

from __future__ import annotations

import logging
from typing import Any, Literal

from egregora.config.site import load_mkdocs_config

EMBEDDING_DIM = 768
logger = logging.getLogger(__name__)
DEFAULT_WRITER_MODEL = "google-gla:gemini-flash-latest"
DEFAULT_ENRICHER_MODEL = "google-gla:gemini-flash-latest"
DEFAULT_ENRICHER_VISION_MODEL = "google-gla:gemini-flash-latest"
DEFAULT_RANKING_MODEL = "google-gla:gemini-flash-latest"
DEFAULT_EDITOR_MODEL = "google-gla:gemini-flash-latest"
DEFAULT_EMBEDDING_MODEL = "google-gla:gemini-embedding-001"
ModelType = Literal["writer", "enricher", "enricher_vision", "ranking", "editor", "embedding"]


def from_pydantic_ai_model(model_name: str) -> str:
    """Convert pydantic-ai string notation to Google API model format.

    Use this ONLY for direct Google GenAI SDK calls (e.g., embeddings).
    Pydantic-AI agents should use the pydantic-ai format directly.

    Examples:
        "google-gla:gemini-flash-latest" -> "models/gemini-flash-latest"
        "google-gla:gemini-2.0-flash-exp" -> "models/gemini-2.0-flash-exp"

    Args:
        model_name: Model name in pydantic-ai format (provider:model)

    Returns:
        Model name in Google API format (models/model-name)

    """
    if ":" in model_name:
        _, model_name = model_name.split(":", 1)
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"
    return model_name


class ModelConfig:
    """Centralized model configuration with fallback hierarchy."""

    def __init__(self, cli_model: str | None = None, site_config: dict[str, Any] | None = None) -> None:
        """Initialize model config with CLI override and site config.

        Args:
            cli_model: Model specified via CLI flag (highest priority)
            site_config: Configuration from mkdocs.yml extra.egregora section

        """
        self.cli_model = cli_model
        self.site_config = site_config or {}

    def get_model(self, model_type: ModelType) -> str:
        """Get model name for a specific task with fallback hierarchy.

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
        if self.cli_model:
            logger.debug("Using CLI model for %s: %s", model_type, self.cli_model)
            return self.cli_model
        models_config = self.site_config.get("models", {})
        if model_type in models_config:
            model = models_config[model_type]
            logger.debug("Using site config model for %s: %s", model_type, model)
            return model
        if "model" in self.site_config:
            model = self.site_config["model"]
            logger.debug("Using global site config model for %s: %s", model_type, model)
            return model
        defaults = {
            "writer": DEFAULT_WRITER_MODEL,
            "enricher": DEFAULT_ENRICHER_MODEL,
            "enricher_vision": DEFAULT_ENRICHER_VISION_MODEL,
            "ranking": DEFAULT_RANKING_MODEL,
            "editor": DEFAULT_EDITOR_MODEL,
            "embedding": DEFAULT_EMBEDDING_MODEL,
        }
        model = defaults[model_type]
        logger.debug("Using default model for %s: %s", model_type, model)
        return model


def load_site_config(output_dir: Path) -> dict[str, Any]:
    """Load egregora configuration from mkdocs.yml if it exists.

    Args:
        output_dir: Output directory (will look for mkdocs.yml in parent/root)

    Returns:
        Dict with egregora config from extra.egregora section

    """
    config, mkdocs_path = load_mkdocs_config(output_dir)
    if not mkdocs_path:
        logger.debug("No mkdocs.yml found, using default config")
        return {}
    egregora_config = config.get("extra", {}).get("egregora", {})
    logger.debug("Loaded site config from %s", mkdocs_path)
    return egregora_config
