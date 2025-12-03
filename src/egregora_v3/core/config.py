from pathlib import Path
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator
import yaml

class ModelSettings(BaseModel):
    """Configuration for LLM models."""
    writer: str = Field(default="google-gla:gemini-2.0-flash", description="Model for writing posts")
    enricher: str = Field(default="google-gla:gemini-2.0-flash", description="Model for enrichment")
    embedding: str = Field(default="models/gemini-embedding-001", description="Model for embeddings")

    # Fallback/Secondary provider
    fallback_enabled: bool = Field(default=True, description="Enable fallback to secondary provider")
    fallback_model: str = Field(default="openrouter:google/gemini-flash-1.5", description="Fallback model ID")

class PathsSettings(BaseModel):
    """
    Path configuration.
    All paths are relative to the 'site_root' unless absolute.
    """
    site_root: Path = Field(default=Path("."), description="Root directory of the site")

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

class EgregoraConfig(BaseModel):
    """
    Root configuration for Egregora V3.
    """
    models: ModelSettings = Field(default_factory=ModelSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def load(cls, site_root: Path) -> "EgregoraConfig":
        """
        Loads configuration from .egregora/config.yml in the site_root.
        If file doesn't exist, returns default config.
        Raises error if file exists but is invalid.
        """
        config_path = site_root / ".egregora" / "config.yml"

        data = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        # Inject site_root into paths config
        # We modify the dictionary before instantiation to ensure immutability/clean construction
        paths_data = data.get("paths", {})
        if isinstance(paths_data, dict):
            paths_data["site_root"] = site_root
            data["paths"] = paths_data
        else:
            # If paths is not a dict (e.g. None or invalid), we set it to a dict with site_root
            # Pydantic validation will handle if the user provided something weird but valid-ish
            data["paths"] = {"site_root": site_root}

        return cls(**data)
