from pathlib import Path
from typing import Tuple, Type

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import TomlConfigSettingsSource


class ModelSettings(BaseModel):
    """Configuration for LLM models."""

    writer: str = Field(default="google-gla:gemini-2.0-flash", description="Model for writing posts")
    enricher: str = Field(default="google-gla:gemini-2.0-flash", description="Model for enrichment")
    embedding: str = Field(default="models/gemini-embedding-001", description="Model for embeddings")


class PathsSettings(BaseModel):
    """Path configuration."""

    site_root: Path = Field(
        default_factory=Path.cwd,
        description="Root directory of the site",
    )
    posts_dir: Path = Path("posts")
    profiles_dir: Path = Path("profiles")
    media_dir: Path = Path("media")
    db_path: Path = Path(".egregora/pipeline.duckdb")
    lancedb_path: Path = Path(".egregora/lancedb")

    # Resolved absolute paths
    abs_posts_dir: Path = Path("")
    abs_profiles_dir: Path = Path("")
    abs_media_dir: Path = Path("")
    abs_db_path: Path = Path("")
    abs_lancedb_path: Path = Path("")

    @model_validator(mode="after")
    def resolve_paths(self) -> "PathsSettings":
        """Resolve all paths relative to the site_root."""
        if not self.site_root.is_absolute():
            self.site_root = Path.cwd() / self.site_root


class EgregoraConfig(BaseSettings):
    """Root configuration for Egregora V3."""

    models: ModelSettings = Field(default_factory=ModelSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)

    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix="EGREGORA_",
        env_nested_delimiter="__",
        toml_file=".egregora.toml",
    )
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )
