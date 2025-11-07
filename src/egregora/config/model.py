"""Centralized Gemini model configuration for all agents.

MODERN (Phase 0): Uses EgregoraConfig from schema.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from egregora.config.loader import load_egregora_config

if TYPE_CHECKING:
    from egregora.config.schema import EgregoraConfig

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
    """Centralized model configuration with CLI override support.

    Uses EgregoraConfig from schema.py as the source of truth.
    """

    def __init__(self, config: EgregoraConfig, cli_model: str | None = None) -> None:
        """Initialize model config.

        Args:
            config: EgregoraConfig instance from .egregora/config.yml
            cli_model: Optional model override from CLI flag (highest priority)

        """
        self.config = config
        self.cli_model = cli_model

    def get_model(self, model_type: ModelType) -> str:
        """Get model name for a specific task.

        Priority:
        1. CLI flag (--model) if provided
        2. Config file (.egregora/config.yml models.{type})
        3. Default for task type

        Args:
            model_type: Type of model to retrieve

        Returns:
            Model name to use

        """
        # CLI override takes precedence
        if self.cli_model:
            logger.debug("Using CLI model for %s: %s", model_type, self.cli_model)
            return self.cli_model

        # Get from config
        model = getattr(self.config.models, model_type, None)
        if model:
            logger.debug("Using config model for %s: %s", model_type, model)
            return model

        # Fall back to defaults
        defaults = {
            "writer": DEFAULT_WRITER_MODEL,
            "enricher": DEFAULT_ENRICHER_MODEL,
            "enricher_vision": DEFAULT_ENRICHER_VISION_MODEL,
            "ranking": DEFAULT_RANKING_MODEL,
            "editor": DEFAULT_EDITOR_MODEL,
            "embedding": DEFAULT_EMBEDDING_MODEL,
        }
        default_model = defaults[model_type]
        logger.debug("Using default model for %s: %s", model_type, default_model)
        return default_model


def get_model_config(site_root: Path, cli_model: str | None = None) -> ModelConfig:
    """Load EgregoraConfig and create ModelConfig.

    Convenience function that combines config loading with ModelConfig creation.

    Args:
        site_root: Root directory containing .egregora/config.yml
        cli_model: Optional CLI model override

    Returns:
        ModelConfig instance

    """
    egregora_config = load_egregora_config(site_root)
    return ModelConfig(config=egregora_config, cli_model=cli_model)
