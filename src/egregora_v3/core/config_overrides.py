"""Utilities for applying validated configuration overrides."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from egregora_v3.core.config import EgregoraConfig


class ConfigOverrideBuilder:
    """Apply validated, chainable overrides to an :class:`EgregoraConfig` instance."""

    def __init__(self, base_config: EgregoraConfig) -> None:
        # Work on a deep copy to avoid mutating caller-provided config
        self._config = base_config.model_copy(deep=True)

    def _apply_updates(self, section_name: str, overrides: dict[str, Any], *, skip_none: bool = True) -> None:
        updates = {key: value for key, value in overrides.items() if not (skip_none and value is None)}
        if updates:
            section = getattr(self._config, section_name)
            setattr(self._config, section_name, section.model_copy(update=updates))

    def with_pipeline(self, **overrides: Any) -> ConfigOverrideBuilder:
        """Apply pipeline-related overrides (e.g., step size, overlap)."""
        self._apply_updates("pipeline", overrides)
        return self

    def with_enrichment(self, **overrides: Any) -> ConfigOverrideBuilder:
        """Apply enrichment-related overrides."""
        # Allow explicit False values to be set, but skip missing (None) values
        self._apply_updates("enrichment", overrides)
        return self

    def with_rag(self, **overrides: Any) -> ConfigOverrideBuilder:
        """Apply RAG-related overrides (retrieval mode, nprobe, overfetch)."""
        self._apply_updates("rag", overrides)
        return self

    def with_models(self, *, model: str | None = None, **overrides: Any) -> ConfigOverrideBuilder:
        """Apply model overrides, including broadcasting a single model to all agents."""
        updates: dict[str, Any] = {key: value for key, value in overrides.items() if value is not None}

        if model:
            updates.update(
                {
                    "writer": model,
                    "enricher": model,
                    "enricher_vision": model,
                    "ranking": model,
                    "editor": model,
                    "reader": model,
                }
            )

        self._apply_updates("models", updates, skip_none=False)
        return self

    def build(self) -> EgregoraConfig:
        """Return the updated configuration instance."""
        return self._config
