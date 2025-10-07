"""Configuration helpers for the MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..config import _ensure_safe_directory
from ..rag.config import RAGConfig, sanitize_rag_config_payload


class MCPServerConfig(BaseModel):
    """Runtime configuration values for the MCP server."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True, validate_assignment=True)

    config_path: Path | None = None
    newsletters_dir: Path = Field(
        default_factory=lambda: _ensure_safe_directory("data/newsletters")
    )
    cache_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("cache/rag"))
    rag: RAGConfig = Field(default_factory=RAGConfig)

    @field_validator("newsletters_dir", "cache_dir", mode="before")
    @classmethod
    def _validate_directories(cls, value: Any) -> Path:
        return _ensure_safe_directory(value)

    @field_validator("rag", mode="before")
    @classmethod
    def _validate_rag(cls, value: Any) -> RAGConfig:
        if isinstance(value, RAGConfig):
            return value
        if isinstance(value, Mapping):
            return RAGConfig(**sanitize_rag_config_payload(dict(value)))
        raise TypeError("rag configuration must be a mapping")

    @classmethod
    def from_path(cls, path: Path | None) -> "MCPServerConfig":
        if not path or not path.exists():
            return cls(config_path=path)

        try:
            data = path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem failures
            raise ValueError(f"Unable to read MCP configuration: {exc}") from exc

        import tomllib

        payload = tomllib.loads(data)
        rag_section = payload.get("rag") if isinstance(payload, Mapping) else None
        rag_data: dict[str, Any] = {}
        newsletters_dir = None
        cache_dir = None

        if isinstance(rag_section, Mapping):
            sanitized_rag = sanitize_rag_config_payload(dict(rag_section))
            newsletters_dir = sanitized_rag.pop("newsletters_dir", None)
            cache_dir = sanitized_rag.pop("cache_dir", None)
            rag_data = sanitized_rag

        return cls(
            config_path=path,
            newsletters_dir=
            newsletters_dir or _ensure_safe_directory("data/newsletters"),
            cache_dir=cache_dir or _ensure_safe_directory("cache/rag"),
            rag=RAGConfig(**rag_data) if rag_data else RAGConfig(),
        )


__all__ = ["MCPServerConfig"]
