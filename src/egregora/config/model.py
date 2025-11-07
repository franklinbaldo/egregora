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

# Model type literal for type checking
ModelType = Literal["writer", "enricher", "enricher_vision", "ranking", "editor", "banner", "embedding"]

# NOTE: Model defaults are centralized in schema.py ModelsConfig class
# No fallback constants needed - schema.py provides non-nullable defaults




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
           - Agent-specific models default to models.default if not specified
           - Resolution happens in schema.py @model_validator

        Args:
            model_type: Type of model to retrieve

        Returns:
            Model name to use

        """
        # CLI override takes precedence
        if self.cli_model:
            logger.debug("Using CLI model for %s: %s", model_type, self.cli_model)
            return self.cli_model

        # Get from config (defaults already resolved by schema validator)
        model = getattr(self.config.models, model_type)
        logger.debug("Using config model for %s: %s", model_type, model)
        return model



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
