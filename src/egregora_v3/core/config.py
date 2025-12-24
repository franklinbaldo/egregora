from pathlib import Path
from typing import Tuple

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
    InitSettingsSource,
)


def find_project_root(start_dir: Path | None = None) -> Path | None:
    """Finds the project root by searching upwards for '.egregora.toml'."""
    current_dir = start_dir or Path.cwd()
    search_path = [current_dir] + list(current_dir.parents)
    for directory in search_path:
        if (directory / ".egregora.toml").is_file():
            return directory
    return None


class ModelSettings(BaseModel):
    """Configuration for LLM models."""

    writer: str = Field(default="google-gla:gemini-2.0-flash", description="Model for writing posts")
    enricher: str = Field(default="google-gla:gemini-2.0-flash", description="Model for enrichment")
    embedding: str = Field(default="models/gemini-embedding-001", description="Model for embeddings")


class PathsSettings(BaseModel):
    """Path configuration."""

    site_root: Path = Field(description="Root directory of the site")
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
            self.site_root = (Path.cwd() / self.site_root).resolve()

        self.abs_posts_dir = self.site_root / self.posts_dir
        self.abs_profiles_dir = self.site_root / self.profiles_dir
        self.abs_media_dir = self.site_root / self.media_dir
        self.abs_db_path = self.site_root / self.db_path
        self.abs_lancedb_path = self.site_root / self.lancedb_path
        return self


class EgregoraConfig(BaseSettings):
    """Root configuration for Egregora V3."""

    models: ModelSettings = Field(default_factory=ModelSettings)
    paths: PathsSettings

    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix="EGREGORA_",
        env_nested_delimiter="__",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:

        project_root = find_project_root()
        site_root_to_inject = project_root or Path.cwd()

        # This source injects the found site_root with high priority
        root_injection_source = InitSettingsSource(
            settings_cls, init_kwargs={"paths": {"site_root": site_root_to_inject}}
        )

        toml_source = None
        if project_root:
            toml_source = TomlConfigSettingsSource(
                settings_cls, toml_file=project_root / ".egregora.toml"
            )

        sources = (
            # Highest priority
            init_settings,
            env_settings,
            root_injection_source,
        )
        if toml_source:
            sources += (toml_source,)

        sources += (
            dotenv_settings,
            file_secret_settings,
            # Lowest priority
        )

        return sources
