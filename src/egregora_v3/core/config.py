from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelSettings(BaseModel):
    """Configuration for LLM models."""

    writer: str = Field(default="google-gla:gemini-2.0-flash", description="Model for writing posts")
    enricher: str = Field(default="google-gla:gemini-2.0-flash", description="Model for enrichment")
    embedding: str = Field(default="models/gemini-embedding-001", description="Model for embeddings")

    # Fallback/Secondary provider
    fallback_enabled: bool = Field(default=True, description="Enable fallback to secondary provider")
    fallback_model: str = Field(default="openrouter:google/gemini-flash-1.5", description="Fallback model ID")


class PathsSettings(BaseModel):
    """Path configuration.

    All paths are relative to the 'site_root' unless absolute.
    """

    site_root: Path = Field(default=Path(), description="Root directory of the site")

    # Content
    posts_dir: Path = Field(default=Path("posts"), description="Posts directory")
    profiles_dir: Path = Field(default=Path("profiles"), description="Profiles directory")
    media_dir: Path = Field(default=Path("media"), description="Media directory")

    # Internal
    egregora_dir: Path = Field(default=Path(".egregora"), description="Internal directory")
    db_path: Path = Field(default=Path(".egregora/pipeline.duckdb"), description="DuckDB file path")
    lancedb_path: Path = Field(default=Path(".egregora/lancedb"), description="LanceDB directory")

    @property
    def abs_posts_dir(self) -> Path:
        return self._resolve(self.posts_dir)

    @property
    def abs_profiles_dir(self) -> Path:
        return self._resolve(self.profiles_dir)

    @property
    def abs_media_dir(self) -> Path:
        return self._resolve(self.media_dir)

    @property
    def abs_db_path(self) -> Path:
        return self._resolve(self.db_path)

    @property
    def abs_lancedb_path(self) -> Path:
        return self._resolve(self.lancedb_path)

    def _resolve(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return self.site_root / path


class PipelineSettings(BaseModel):
    """Pipeline execution settings."""

    step_size: int = 1
    step_unit: Literal["days", "messages", "hours"] = "days"
    max_tokens: int = 100_000


class EgregoraConfig(BaseSettings):
    """Root configuration for Egregora V3.

    Supports environment variable overrides with the pattern:
    EGREGORA_SECTION__KEY (e.g., EGREGORA_MODELS__WRITER)
    """

    models: ModelSettings = Field(default_factory=ModelSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)

    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix="EGREGORA_",
        env_nested_delimiter="__",
    )

    @classmethod
    def load(cls, site_root: Path) -> "EgregoraConfig":
        """Loads configuration from .egregora/config.yml and environment variables.

        Uses ConfigLoader to handle YAML file loading. Environment variables
        automatically override file values via Pydantic Settings.

        Priority (highest to lowest):
        1. Environment variables (EGREGORA_SECTION__KEY)
        2. Config file (.egregora/config.yml)
        3. Defaults

        Returns:
            EgregoraConfig: Fully loaded and validated configuration.

        Raises:
            ValueError: If config file exists but contains invalid YAML.
        """
        from egregora_v3.core.config_loader import ConfigLoader

        return ConfigLoader(site_root).load()
