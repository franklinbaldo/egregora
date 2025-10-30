"""Utilities for reading MkDocs configuration and deriving site paths."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar, overload

import yaml

logger = logging.getLogger(__name__)

DEFAULT_DOCS_DIR = "docs"
DEFAULT_BLOG_DIR = "posts"
PROFILES_DIR_NAME = "profiles"
MEDIA_DIR_NAME = "media"


_T = TypeVar("_T")


class _ConfigLoader(yaml.SafeLoader):
    """YAML loader that tolerates MkDocs plugin tags."""


def _construct_python_name(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> str:
    """Return python/name tags as plain strings."""

    return loader.construct_scalar(node)


_ConfigLoader.add_multi_constructor("tag:yaml.org,2002:python/name", _construct_python_name)


@dataclass(frozen=True, slots=True)
class SitePaths:
    """Resolved paths for an Egregora MkDocs site."""

    site_root: Path
    mkdocs_path: Path | None
    docs_dir: Path
    blog_dir: str
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path
    rankings_dir: Path
    rag_dir: Path
    enriched_dir: Path
    config: "MkDocsConfig"


@dataclass(frozen=True, slots=True)
class MkDocsConfig(Mapping[str, object]):
    """Typed representation of the ``mkdocs.yml`` payload we care about."""

    docs_dir: str | None = None
    plugins: Sequence[str | Mapping[str, object]] = field(default_factory=tuple)
    _data: Mapping[str, object] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        normalized = self._normalize_mapping(self._data)
        object.__setattr__(self, "_data", normalized)

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    @overload
    def get(self, key: str, default: None = None) -> object | None: ...

    @overload
    def get(self, key: str, default: _T) -> object | _T: ...

    def get(self, key: str, default: _T | None = None) -> object | _T | None:
        return self._data.get(key, default)

    @classmethod
    def empty(cls) -> "MkDocsConfig":
        return cls()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "MkDocsConfig":
        if data is None:
            return cls.empty()

        docs_dir = cls._coerce_docs_dir(data.get("docs_dir"))
        plugins = cls._coerce_plugins(data.get("plugins"))
        return cls(docs_dir=docs_dir, plugins=plugins, _data=data)

    @staticmethod
    def _coerce_docs_dir(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _coerce_plugins(value: Any) -> tuple[str | Mapping[str, object], ...]:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            plugins: list[str | Mapping[str, object]] = []
            for item in value:
                if isinstance(item, str):
                    plugins.append(item)
                elif isinstance(item, Mapping):
                    plugins.append(item)
            return tuple(plugins)
        return ()

    @staticmethod
    def _normalize_mapping(data: Mapping[str, Any]) -> Mapping[str, object]:
        normalized: dict[str, object] = {}
        for key, value in data.items():
            normalized[str(key)] = value
        return normalized


def find_mkdocs_file(start: Path) -> Path | None:
    """Search upward from ``start`` for ``mkdocs.yml``."""
    current = start.expanduser().resolve()
    for candidate in (current, *current.parents):
        mkdocs_path = candidate / "mkdocs.yml"
        if mkdocs_path.exists():
            return mkdocs_path
    return None


def load_mkdocs_config(start: Path) -> tuple[MkDocsConfig, Path | None]:
    """Load ``mkdocs.yml`` into a :class:`MkDocsConfig` wrapper."""
    mkdocs_path = find_mkdocs_file(start)
    if not mkdocs_path:
        return MkDocsConfig.empty(), None

    raw_config = yaml.load(mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader)
    if raw_config is None:
        config = MkDocsConfig.empty()
    elif isinstance(raw_config, Mapping):
        config = MkDocsConfig.from_mapping(raw_config)
    else:
        logger.warning("mkdocs.yml at %s did not parse into a mapping; ignoring", mkdocs_path)
        config = MkDocsConfig.empty()

    return config, mkdocs_path


def _resolve_docs_dir(site_root: Path, config: MkDocsConfig) -> Path:
    """Return the absolute docs directory based on MkDocs config."""
    docs_setting = config.docs_dir if config.docs_dir not in (None, "") else DEFAULT_DOCS_DIR
    docs_setting = "." if docs_setting in ("./", "") else docs_setting

    if docs_setting in (".", None):
        return site_root

    docs_path = Path(str(docs_setting))
    if docs_path.is_absolute():
        return docs_path
    return (site_root / docs_path).resolve()


def _extract_blog_dir(config: MkDocsConfig) -> str | None:
    """Extract blog_dir from the blog plugin configuration."""
    for plugin in config.plugins:
        if isinstance(plugin, str):
            if plugin == "blog":
                return DEFAULT_BLOG_DIR
            continue

        blog_config = plugin.get("blog") if isinstance(plugin, Mapping) else None
        if isinstance(blog_config, Mapping):
            blog_dir = blog_config.get("blog_dir")
            if blog_dir is None:
                return DEFAULT_BLOG_DIR
            if isinstance(blog_dir, str):
                return blog_dir
            return str(blog_dir)

    return None


def resolve_site_paths(start: Path) -> SitePaths:
    """Resolve all important directories for the site."""
    start = start.expanduser().resolve()
    config, mkdocs_path = load_mkdocs_config(start)
    site_root = mkdocs_path.parent if mkdocs_path else start

    docs_dir = _resolve_docs_dir(site_root, config)
    blog_dir = _extract_blog_dir(config) or DEFAULT_BLOG_DIR

    blog_path = Path(blog_dir)
    if blog_path.is_absolute():
        posts_dir = blog_path
    else:
        posts_dir = (docs_dir / blog_path).resolve()

    profiles_dir = (docs_dir / PROFILES_DIR_NAME).resolve()
    media_dir = (docs_dir / MEDIA_DIR_NAME).resolve()
    rankings_dir = (site_root / "rankings").resolve()
    rag_dir = (site_root / "rag").resolve()
    enriched_dir = (site_root / "enriched").resolve()

    return SitePaths(
        site_root=site_root,
        mkdocs_path=mkdocs_path,
        docs_dir=docs_dir,
        blog_dir=blog_dir,
        posts_dir=posts_dir,
        profiles_dir=profiles_dir,
        media_dir=media_dir,
        rankings_dir=rankings_dir,
        rag_dir=rag_dir,
        enriched_dir=enriched_dir,
        config=config,
    )


__all__ = [
    "MkDocsConfig",
    "SitePaths",
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "find_mkdocs_file",
    "load_mkdocs_config",
    "resolve_site_paths",
]
