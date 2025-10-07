"""Tests for the ``egregora sync`` Typer command."""

from __future__ import annotations

import shutil
import textwrap
import uuid
from pathlib import Path

import pytest
from typer.testing import CliRunner

from egregora.__main__ import app


runner = CliRunner()


@pytest.fixture()
def local_exports_dir() -> Path:
    root = Path.cwd() / "tests" / "_tmp_cli_sync" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
        parent = root.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        textwrap.dedent(
            """
            [pipeline.remote_source]
            gdrive_url = "https://drive.google.com/folders/mock"
        """
        ).strip()
    )
    return config_path


def test_sync_command_reports_new_archives(
    monkeypatch, local_exports_dir: Path, config_file: Path
) -> None:
    exports_dir = local_exports_dir
    (exports_dir / "existing.zip").write_text("original")

    created: list[Path] = []

    def fake_sync_remote_zips(url: str, target_dir: Path, *, logger=None):  # type: ignore[override]
        first = target_dir / "2024-05-01-grupo.zip"
        first.write_text("dummy")
        nested_dir = target_dir / "outros"
        nested_dir.mkdir(exist_ok=True)
        second = nested_dir / "2024-05-02-grupo.zip"
        second.write_text("dummy")
        created.extend([first, second])
        return [str(first), str(second)]

    monkeypatch.setattr(
        "egregora.remote_sync.sync_remote_zips",
        fake_sync_remote_zips,
        raising=True,
    )

    result = runner.invoke(
        app,
        [
            "sync",
            "--config",
            str(config_file),
            "--zips-dir",
            str(exports_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Foram sincronizados" in result.stdout
    assert "arquivo(s)" in result.stdout

    for path in created:
        rel = path.relative_to(exports_dir)
        assert str(rel) in result.stdout


def test_sync_command_requires_remote_url(local_exports_dir: Path) -> None:
    exports_dir = local_exports_dir

    result = runner.invoke(
        app,
        [
            "sync",
            "--zips-dir",
            str(exports_dir),
        ],
    )

    assert result.exit_code == 1
    assert "Nenhuma URL remota" in result.stdout
