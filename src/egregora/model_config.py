"""Centralized Gemini model configuration for all agents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from .site_config import load_mkdocs_config

DEFAULT_EMBEDDING_DIMENSIONALITY = 3072

# Known output dimensionalities for supported embedding models. The keys should
# match the fully-qualified Gemini model identifiers returned by
# ``ModelConfig.get_model("embedding")``.
KNOWN_EMBEDDING_DIMENSIONS = {
    "models/text-embedding-004": 3072,
    "models/gemini-embedding-001": 3072,
}

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
        self.embedding_output_dimensionality = (
            self._resolve_embedding_output_dimensionality()
        )

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
        # TENET-BREAK(api)[@franklin][P1][due:2025-12-01]:
        # tenet=no-defensive; why=defensive path; exit=remove defensive path
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

    def _resolve_embedding_output_dimensionality(self) -> int:
        """Determine the embedding vector dimensionality for the active model."""

        candidate_keys = (
            ("embedding", "output_dimensionality"),
            ("embedding", "dimensionality"),
            ("embedding", "dimensions"),
        )

        for parent_key, child_key in candidate_keys:
            section = self.site_config.get(parent_key, {})
            if isinstance(section, dict) and child_key in section:
                value = section[child_key]
                try:
                    return int(value)
                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid embedding dimensionality %r for key %s.%s",
                        value,
                        parent_key,
                        child_key,
                    )

        flat_keys = (
            "embedding_output_dimensionality",
            "embedding_dimensionality",
            "embedding_dimensions",
        )

        for key in flat_keys:
            if key in self.site_config:
                value = self.site_config[key]
                try:
                    return int(value)
                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid embedding dimensionality %r for key %s", value, key
                    )

        resolved_model = self.get_model("embedding")
        if resolved_model in KNOWN_EMBEDDING_DIMENSIONS:
            return KNOWN_EMBEDDING_DIMENSIONS[resolved_model]

        logger.warning(
            "Unknown embedding dimensionality for %s; defaulting to %d. "
            "Configure extra.egregora.embedding.output_dimensionality to override.",
            resolved_model,
            DEFAULT_EMBEDDING_DIMENSIONALITY,
        )
        return DEFAULT_EMBEDDING_DIMENSIONALITY

    def get_embedding_output_dimensionality(
        self, model_name: str | None = None
    ) -> int:
        """Return the cached embedding vector dimensionality.

        Args:
            model_name: Ignored. Present for compatibility with older call sites.
        """

        if model_name and model_name != self.get_model("embedding"):
            logger.debug(
                "Embedding dimensionality requested for %s, but ModelConfig is "
                "configured for %s. Returning cached dimensionality.",
                model_name,
                self.get_model("embedding"),
            )
        return self.embedding_output_dimensionality


def load_site_config(output_dir: Path) -> dict:
    """
    Load egregora configuration from mkdocs.yml if it exists.

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
    logger.debug(f"Loaded site config from {mkdocs_path}")
    return egregora_config
