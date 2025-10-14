"""Tests for the MkDocs static site builder."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from egregora.config import PipelineConfig
from egregora.static.builder import (
    MkDocsExecutionError,
    MkDocsNotInstalledError,
    StaticSiteBuilder,
)


def _create_workspace() -> Path:
    root = Path("tmp-tests") / f"static-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_sync_posts_copies_files_and_writes_index() -> None:
    workspace = _create_workspace()
    posts_dir = workspace / "generated"
    posts_dir.mkdir()
    post_file = posts_dir / "2025-01-01-grupo.md"
    post_file.write_text("# Dia 1\n\nResumo do primeiro dia.", encoding="utf-8")

    config = PipelineConfig(posts_dir=posts_dir)
    config.static_site.docs_dir = workspace / "docs"
    config.static_site.site_dir = workspace / "site"

    builder = StaticSiteBuilder(config)
    copied = builder.sync_posts()

    destination = builder.destination_dir / post_file.name
    assert destination.exists()
    assert destination.read_text(encoding="utf-8").startswith("# Dia 1")
    assert copied == [destination]

    index_path = builder.destination_dir / "index.md"
    index_content = index_path.read_text(encoding="utf-8")
    assert "Últimas publicações" in index_content
    assert "Resumo do primeiro dia." in index_content


def test_build_site_invokes_mkdocs(monkeypatch) -> None:
    workspace = _create_workspace()
    posts_dir = workspace / "generated"
    posts_dir.mkdir()

    config = PipelineConfig(posts_dir=posts_dir)
    config.static_site.docs_dir = workspace / "docs"
    config.static_site.site_dir = workspace / "site"
    config.static_site.mkdocs_config = workspace / "mkdocs.yml"
    config.static_site.mkdocs_config.write_text("site_name: Teste", encoding="utf-8")

    builder = StaticSiteBuilder(config)

    calls: list[list[str]] = []

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/mkdocs")
    monkeypatch.setattr(
        "egregora.static.builder.subprocess.run",
        lambda command, check: calls.append(command) or None,
    )

    builder.build_site()

    assert calls
    assert calls[0][0] == "/usr/bin/mkdocs"
    assert calls[0][1:3] == ["build", "-f"]


def test_build_site_raises_when_mkdocs_missing(monkeypatch) -> None:
    workspace = _create_workspace()
    posts_dir = workspace / "generated"
    posts_dir.mkdir()

    config = PipelineConfig(posts_dir=posts_dir)
    config.static_site.docs_dir = workspace / "docs"
    config.static_site.site_dir = workspace / "site"

    builder = StaticSiteBuilder(config)

    monkeypatch.setattr(shutil, "which", lambda _: None)

    with pytest.raises(MkDocsNotInstalledError):
        builder.build_site()


def test_run_command_propagates_failures(monkeypatch) -> None:
    workspace = _create_workspace()
    posts_dir = workspace / "generated"
    posts_dir.mkdir()

    config = PipelineConfig(posts_dir=posts_dir)
    config.static_site.docs_dir = workspace / "docs"
    config.static_site.site_dir = workspace / "site"

    builder = StaticSiteBuilder(config)

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/mkdocs")
    monkeypatch.setattr(
        "egregora.static.builder.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, ["mkdocs"])
        ),
    )

    with pytest.raises(MkDocsExecutionError):
        builder.build_site()
