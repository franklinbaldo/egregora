"""Configuration helpers for the MCP server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ..config import RAGConfig

try:  # Python 3.11+
    import tomllib as toml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for Py311-
    import tomli as toml  # type: ignore


@dataclass(slots=True)
class MCPServerConfig:
    """Runtime configuration values for the MCP server."""

    config_path: Path | None = None
    newsletters_dir: Path = Path("newsletters")
    cache_dir: Path = Path("cache") / "rag"
    rag: RAGConfig = RAGConfig()

    @classmethod
    def from_path(cls, path: Path | None) -> "MCPServerConfig":
        if not path or not path.exists():
            return cls(config_path=path)

        data = toml.loads(path.read_text(encoding="utf-8"))
        rag_data = data.get("rag", {}) if isinstance(data, Mapping) else {}

        rag_kwargs: dict[str, object] = {}
        cache_dir = cls.cache_dir
        newsletters_dir = cls.newsletters_dir

        if isinstance(rag_data, Mapping):
            allowed = set(RAGConfig.__dataclass_fields__.keys())
            for key, value in rag_data.items():
                if key in {"cache_dir", "newsletters_dir"}:
                    if key == "cache_dir":
                        cache_dir = Path(value)
                    else:
                        newsletters_dir = Path(value)
                    continue
                if key in allowed:
                    rag_kwargs[key] = value

        rag_config = RAGConfig(**rag_kwargs) if rag_kwargs else RAGConfig()
        return cls(
            config_path=path,
            newsletters_dir=newsletters_dir.expanduser(),
            cache_dir=cache_dir.expanduser(),
            rag=rag_config,
        )


__all__ = ["MCPServerConfig"]
