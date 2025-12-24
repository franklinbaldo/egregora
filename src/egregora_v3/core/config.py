import tomllib
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        """Loads configuration from .egregora.toml and environment variables.

        Priority (highest to lowest):
        1. Environment variables (EGREGORA_SECTION__KEY)
        2. Config file (.egregora.toml)
        3. Defaults

        Args:
            site_root: Root directory of the site. If None, uses current working directory.

        Returns:
            EgregoraConfig: Fully loaded and validated configuration.
        """
        root_path = site_root if site_root is not None else Path.cwd()
        config_file = root_path / ".egregora.toml"

        file_settings = {}
        if config_file.is_file():
            try:
                with config_file.open("rb") as f:
                    file_settings = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                msg = f"Invalid TOML in {config_file}: {e}"
                raise ValueError(msg) from e

        # Ensure paths section exists for site_root injection
        if "paths" not in file_settings:
            file_settings["paths"] = {}
        file_settings["paths"]["site_root"] = root_path

        # Pydantic will merge dicts during initialization.
        # Env vars take precedence over init_kwargs.
        return cls(**file_settings)
