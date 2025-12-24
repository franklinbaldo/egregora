import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _deep_merge(destination: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Merge source into destination, with source values overwriting."""
    for key, value in source.items():
        if isinstance(value, Mapping) and key in destination and isinstance(destination[key], Mapping):
            destination[key] = _deep_merge(destination.get(key, {}), value)
        else:
            destination[key] = value
    return destination


class ModelSettings(BaseModel):
    """Configuration for LLM models."""

    writer: str = Field(default="google-gla:gemini-2.0-flash", description="Model for writing posts")
    enricher: str = Field(default="google-gla:gemini-2.0-flash", description="Model for enrichment")
    embedding: str = Field(default="models/gemini-embedding-001", description="Model for embeddings")


class PathsSettings(BaseModel):
    """Path configuration.

    All paths are relative to the 'site_root' unless absolute.
    site_root defaults to current working directory.
    """

    site_root: Path = Field(
        default_factory=Path.cwd,
        description="Root directory of the site (defaults to current working directory)",
    )

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


class EgregoraConfig(BaseSettings):
    """Root configuration for Egregora V3.

    Supports environment variable overrides with the pattern:
    EGREGORA_SECTION__KEY (e.g., EGREGORA_MODELS__WRITER)
    """

    models: ModelSettings = Field(default_factory=ModelSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)

    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix="EGREGORA_",
        env_nested_delimiter="__",
    )

    @classmethod
    def load(cls, site_root: Path | None = None) -> "EgregoraConfig":
        # FIXME: This manual merging is more complex than ideal.
        # It's a workaround for the fact that `pydantic-settings` gives
        # `__init__` arguments higher precedence than environment variables,
        # which complicates loading a dynamic TOML file while respecting
        # `env > toml` priority. A future refactoring could explore a custom
        # settings source to simplify this.
        """Loads configuration from .egregora.toml and environment variables.

        Priority (highest to lowest):
        1. Environment variables (EGREGORA_SECTION__KEY)
        2. Config file (.egregora.toml)
        3. Defaults
        """
        root_path = site_root if site_root is not None else Path.cwd()
        config_file = root_path / ".egregora.toml"

        # 1. Load from TOML file
        file_settings: dict[str, Any] = {}
        if config_file.is_file():
            with config_file.open("rb") as f:
                file_settings = tomllib.load(f)

        # 2. Load from environment variables
        env_config = cls()
        env_settings = env_config.model_dump(exclude_unset=True)

        # 3. Merge configurations: env > toml
        merged_config = _deep_merge(file_settings, env_settings)

        # 4. Inject site_root
        merged_config.setdefault("paths", {})["site_root"] = root_path

        # 5. Validate and build the final model object
        return cls.model_validate(merged_config)
