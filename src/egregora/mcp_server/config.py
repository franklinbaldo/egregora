"""Configuration helpers for the MCP server."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import (
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    SecretsSettingsSource,
    TomlConfigSettingsSource,
)

from ..config import _ensure_safe_directory
from ..rag.config import RAGConfig


class MCPServerTomlSettingsSource(TomlConfigSettingsSource):
    """Normalise ``egregora.toml`` payloads for :class:`MCPServerConfig`."""

    def __call__(self) -> dict[str, Any]:
        raw = super().__call__()
        if not raw:
            return {}

        payload: dict[str, Any] = {}
        rag_section = raw.get("rag")
        if isinstance(rag_section, Mapping):
            rag_data = dict(rag_section)
            posts_dir = rag_data.pop("posts_dir", None)
            cache_dir = rag_data.pop("cache_dir", None)
            if posts_dir is not None:
                payload["posts_dir"] = posts_dir
            if cache_dir is not None:
                payload["cache_dir"] = cache_dir
            payload["rag"] = rag_data
        elif rag_section is not None:
            payload["rag"] = rag_section

        return payload


class MCPServerConfig(BaseSettings):
    """Runtime configuration values for the MCP server."""

    model_config = SettingsConfigDict(
        extra="forbid", arbitrary_types_allowed=True, validate_assignment=True
    )

    default_toml_path: ClassVar[Path | None] = Path("egregora.toml")

    config_path: Path | None = None
    posts_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("data"))
    cache_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("cache/rag"))
    rag: RAGConfig = Field(default_factory=RAGConfig)

    @field_validator("posts_dir", "cache_dir", mode="before")
    @classmethod
    def _validate_directories(cls, value: Any) -> Path:
        return _ensure_safe_directory(value)

    @field_validator("rag", mode="before")
    @classmethod
    def _validate_rag(cls, value: Any) -> RAGConfig:
        if isinstance(value, RAGConfig):
            return value
        if isinstance(value, Mapping):
            return RAGConfig(**dict(value))
        raise TypeError("rag configuration must be a mapping")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: EnvSettingsSource,
        dotenv_settings: DotEnvSettingsSource,
        file_secret_settings: SecretsSettingsSource,
    ) -> tuple[InitSettingsSource, ...]:
        toml_source = MCPServerTomlSettingsSource(
            settings_cls,
            getattr(settings_cls, "default_toml_path", None),
        )
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            toml_source,
            file_secret_settings,
        )

    @classmethod
    def load(cls, *, toml_path: Path | None = None) -> MCPServerConfig:
        overrides: dict[str, Any] = {}
        if toml_path is not None:
            overrides["config_path"] = toml_path

        if toml_path is None or not toml_path.exists():
            return cls(**overrides)

        if not toml_path.is_file():
            raise ValueError(f"MCP configuration path '{toml_path}' must be a file")

        original_path = cls.default_toml_path
        cls.default_toml_path = toml_path

        try:
            return cls(**overrides)
        except OSError as exc:  # pragma: no cover - filesystem failures
            raise ValueError(f"Unable to read MCP configuration: {exc}") from exc
        finally:
            cls.default_toml_path = original_path

    @classmethod
    def from_path(cls, path: Path | None) -> MCPServerConfig:
        """Backwards compatible wrapper around :meth:`load`."""

        return cls.load(toml_path=path)


__all__ = ["MCPServerConfig"]
