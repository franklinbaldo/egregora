from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass
class SitePaths:
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
    config: dict[str, Any]


def find_mkdocs_file(start: Path) -> Path | None: ...

def resolve_site_paths(start: Path) -> SitePaths: ...
