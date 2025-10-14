"""Utilities for building and previewing the MkDocs static site."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..config import PipelineConfig


class StaticSiteError(RuntimeError):
    """Base error for the static site subsystem."""


class MkDocsNotInstalledError(StaticSiteError):
    """Raised when the ``mkdocs`` binary is not available on ``PATH``."""


class MkDocsExecutionError(StaticSiteError):
    """Raised when MkDocs commands fail to execute correctly."""


@dataclass(slots=True)
class PostSummary:
    """Lightweight description of a generated post used for index pages."""

    filename: str
    title: str
    summary: str


class StaticSiteBuilder:
    """Synchronise generated posts with MkDocs and manage previews."""

    def __init__(self, config: PipelineConfig, mkdocs_bin: str = "mkdocs") -> None:
        self._config = config
        self._mkdocs_bin = mkdocs_bin

    @property
    def destination_dir(self) -> Path:
        """Return the directory where MkDocs expects the posts."""

        static_config = self._config.static_site
        return static_config.docs_dir / static_config.posts_output_dir

    def sync_posts(self, posts_dir: Path | None = None) -> list[Path]:
        """Copy generated Markdown posts into the MkDocs docs tree."""

        source_dir = posts_dir or self._config.posts_dir
        destination_dir = self.destination_dir
        destination_dir.mkdir(parents=True, exist_ok=True)

        copied: list[Path] = []
        summaries: list[PostSummary] = []

        for post in sorted(source_dir.glob("*.md")):
            destination = destination_dir / post.name
            if post.resolve() != destination.resolve():
                destination.write_text(post.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(destination)
            summaries.append(self._build_summary(destination))

        self._write_index(destination_dir, summaries)
        return copied

    def build_site(self) -> None:
        """Invoke ``mkdocs build`` using the configured paths."""

        mkdocs_path = self._resolve_mkdocs()
        static_config = self._config.static_site
        command = [
            mkdocs_path,
            "build",
            "-f",
            str(static_config.mkdocs_config),
            "-d",
            str(static_config.site_dir),
        ]
        self._run_command(command, "mkdocs build")

    def serve_site(self) -> None:
        """Run ``mkdocs serve`` for live previews until the user stops it."""

        mkdocs_path = self._resolve_mkdocs()
        static_config = self._config.static_site
        command = [
            mkdocs_path,
            "serve",
            "-f",
            str(static_config.mkdocs_config),
            "-a",
            f"{static_config.preview_host}:{static_config.preview_port}",
        ]
        self._run_command(command, "mkdocs serve", allow_keyboard_interrupt=True)

    def _resolve_mkdocs(self) -> str:
        candidate = shutil.which(self._mkdocs_bin)
        if not candidate:
            raise MkDocsNotInstalledError(
                "mkdocs não está disponível no PATH; instale mkdocs>=1.6 para habilitar prévias"
            )
        return candidate

    def _run_command(
        self,
        command: list[str],
        description: str,
        *,
        allow_keyboard_interrupt: bool = False,
    ) -> None:
        try:
            subprocess.run(command, check=True)
        except KeyboardInterrupt:
            if allow_keyboard_interrupt:
                return
            raise
        except subprocess.CalledProcessError as exc:  # pragma: no cover - exercised via tests
            raise MkDocsExecutionError(
                f"Falha ao executar {description}: código de saída {exc.returncode}"
            ) from exc

    def _build_summary(self, path: Path) -> PostSummary:
        content = path.read_text(encoding="utf-8")
        title = path.stem.replace("-", " ").title()
        summary = ""

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("---"):
                continue
            if stripped.startswith("#"):
                title = stripped.lstrip("# ")
                continue
            summary = stripped
            break

        return PostSummary(filename=path.name, title=title, summary=summary)

    def _write_index(self, destination_dir: Path, summaries: Iterable[PostSummary]) -> None:
        index_path = destination_dir / "index.md"
        lines = ["# Últimas publicações", ""]

        summaries_list = list(summaries)
        if not summaries_list:
            lines.append("Nenhum post gerado até o momento.")
        else:
            for summary in sorted(summaries_list, key=lambda item: item.filename, reverse=True):
                lines.append(f"- [{summary.title}]({summary.filename})")
                if summary.summary:
                    lines.append(f"  - {summary.summary}")

        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "MkDocsExecutionError",
    "MkDocsNotInstalledError",
    "StaticSiteBuilder",
]
