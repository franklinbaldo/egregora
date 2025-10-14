"""Tests covering the new generation CLI and helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
import shutil

import polars as pl
import pytest
from typer.testing import CliRunner

from egregora.archive.uploader import ArchiveUploadError, ArchiveUploadResult
from egregora.generate.cli import generate_app
from egregora.generate.core import FastMCPContextClient, PromptRenderer
from egregora.rag_context.server import SearchResponse
from egregora.static.builder import MkDocsNotInstalledError


def test_prompt_renderer_includes_rag_context() -> None:
    renderer = PromptRenderer()
    prompt = renderer.render(
        group_name="Grupo Teste",
        today=date(2025, 1, 1),
        transcripts=[(date(2025, 1, 1), "Mensagem A")],
        previous_post=None,
        enrichment_section=None,
        rag_snippets=["Lembramos do debate sobre IA"],
        rag_records=[],
    )

    assert "Lembramos do debate sobre IA" in prompt
    assert "TRANSCRITO_2025-01-01_INICIO" in prompt


class _StubCallResult:
    def __init__(self, data: Any) -> None:
        self.data = data
        self.structured_content = None
        self.content = []


class _StubClient:
    def __init__(self, transport: str, timeout: float = 0.0) -> None:
        self.transport = transport
        self.timeout = timeout

    async def __aenter__(self) -> "_StubClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def call_tool(self, name: str, payload: dict[str, Any], timeout: float | None = None) -> _StubCallResult:
        return _StubCallResult(
            SearchResponse(
                query=payload["query"],
                k=payload["k"],
                min_similarity=payload.get("min_similarity", 0.0),
                snippets=["Primeiro contexto", "Segundo contexto"],
                results=[{"message": "Primeiro contexto", "similarity": 0.9}],
            )
        )


def test_fastmcp_context_client_normalises_payload() -> None:
    client = FastMCPContextClient("http://example.com", client_cls=_StubClient)
    result = client.search("Consulta de teste", top_k=2, min_similarity=0.5)

    assert result.snippets[0] == "Primeiro contexto"
    assert result.records[0]["message"] == "Primeiro contexto"


@pytest.mark.parametrize("file_suffix", [".parquet", ".csv"])
def test_generate_cli_dry_run(monkeypatch, tmp_path: Path, file_suffix: str) -> None:
    data = {
        "date": [date(2025, 1, 1)],
        "time": ["09:00"],
        "anon_author": ["Member-AAAA"],
        "message": ["Mensagem inicial"],
        "group_name": ["Grupo Dry"],
        "group_slug": ["grupo-dry"],
    }
    frame = pl.DataFrame(data)

    dataset_path = tmp_path / f"dataset{file_suffix}"
    if file_suffix == ".parquet":
        frame.write_parquet(dataset_path)
    else:
        frame.write_csv(dataset_path)

    monkeypatch.setattr(
        "egregora.generate.core.PostGenerator.generate",
        lambda self, source, context: "Conteúdo simulado",
    )

    runner = CliRunner()
    result = runner.invoke(generate_app, ["--dry-run", "--show", str(dataset_path)])

    assert result.exit_code == 0
    assert "Conteúdo simulado" in result.stdout


def test_generate_cli_build_static_invokes_builder(monkeypatch, tmp_path: Path) -> None:
    data = {
        "date": [date(2025, 1, 1)],
        "time": ["09:00"],
        "anon_author": ["Member-AAAA"],
        "message": ["Mensagem"],
        "group_name": ["Grupo"],
        "group_slug": ["grupo"],
    }
    frame = pl.DataFrame(data)
    dataset_path = tmp_path / "dataset.parquet"
    frame.write_parquet(dataset_path)

    output_dir = Path("tmp-tests") / f"gen-{date.today().isoformat()}"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    monkeypatch.setattr(
        "egregora.generate.core.PostGenerator.generate",
        lambda self, source, context: "Conteúdo",
    )

    calls: dict[str, int] = {"sync": 0, "build": 0, "serve": 0}

    class _Builder:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def sync_posts(self, *_args, **_kwargs):
            calls["sync"] += 1
            return []

        @property
        def destination_dir(self) -> Path:
            return output_dir

        def build_site(self) -> None:
            calls["build"] += 1

        def serve_site(self) -> None:
            calls["serve"] += 1

    monkeypatch.setattr("egregora.generate.cli.StaticSiteBuilder", _Builder)

    runner = CliRunner()
    result = runner.invoke(
        generate_app,
        [
            "--output",
            str(output_dir),
            "--build-static",
            str(dataset_path),
        ],
    )

    assert result.exit_code == 0
    assert calls["sync"] == 1
    assert calls["build"] == 1
    assert calls["serve"] == 0


def test_generate_cli_preview_invokes_serve(monkeypatch, tmp_path: Path) -> None:
    data = {
        "date": [date(2025, 1, 1)],
        "time": ["09:00"],
        "anon_author": ["Member-AAAA"],
        "message": ["Mensagem"],
        "group_name": ["Grupo"],
        "group_slug": ["grupo"],
    }
    frame = pl.DataFrame(data)
    dataset_path = tmp_path / "dataset.parquet"
    frame.write_parquet(dataset_path)

    output_dir = Path("tmp-tests") / f"preview-{date.today().isoformat()}"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    monkeypatch.setattr(
        "egregora.generate.core.PostGenerator.generate",
        lambda self, source, context: "Conteúdo",
    )

    class _Builder:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def sync_posts(self, *_args, **_kwargs):
            return []

        @property
        def destination_dir(self) -> Path:
            return output_dir

        def build_site(self) -> None:
            return None

        def serve_site(self) -> None:
            raise MkDocsNotInstalledError("mkdocs ausente")

    monkeypatch.setattr("egregora.generate.cli.StaticSiteBuilder", _Builder)

    runner = CliRunner()
    result = runner.invoke(
        generate_app,
        [
            "--output",
            str(output_dir),
            "--no-build-static",
            "--preview",
            str(dataset_path),
        ],
    )

    assert result.exit_code == 1
    assert "mkdocs ausente" in result.stdout


def test_generate_cli_archive_invokes_manager(monkeypatch, tmp_path: Path) -> None:
    data = {
        "date": [date(2025, 1, 1)],
        "time": ["09:00"],
        "anon_author": ["Member-AAAA"],
        "message": ["Mensagem"],
        "group_name": ["Grupo"],
        "group_slug": ["grupo"],
    }
    frame = pl.DataFrame(data)
    dataset_path = tmp_path / "dataset.parquet"
    frame.write_parquet(dataset_path)

    monkeypatch.setattr(
        "egregora.generate.core.PostGenerator.generate",
        lambda self, source, context: "Conteúdo",
    )

    class _Builder:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def sync_posts(self, *_args, **_kwargs):
            return []

        @property
        def destination_dir(self) -> Path:
            return dataset_path.parent

        def build_site(self) -> None:
            return None

        def serve_site(self) -> None:
            return None

    monkeypatch.setattr("egregora.generate.cli.StaticSiteBuilder", _Builder)

    calls: dict[str, object] = {"upload": 0}

    class _StubArchiveManager:
        def __init__(self, config) -> None:  # noqa: ANN001
            calls["enabled"] = config.archive.enabled

        def upload_dataset(  # noqa: ANN001
            self,
            dataset: Path,
            *,
            identifier: str | None = None,
            suffix: str | None = None,
            metadata: dict[str, str] | None = None,
            dry_run: bool = False,
        ) -> ArchiveUploadResult:
            calls["upload"] += 1
            calls["identifier"] = identifier
            calls["suffix"] = suffix
            calls["metadata"] = metadata or {}
            calls["dry_run"] = dry_run
            return ArchiveUploadResult(
                identifier=identifier or "egregora-vectors-20250101",
                source=dataset,
                local_copy=Path("data/exports") / "egregora-vectors-20250101.parquet",
                metadata=metadata or {},
                dry_run=dry_run,
            )

    monkeypatch.setattr("egregora.generate.cli.ArchiveManager", _StubArchiveManager)

    runner = CliRunner()
    result = runner.invoke(
        generate_app,
        [
            "--archive",
            "--archive-suffix",
            "lote-42",
            "--archive-meta",
            "project=egregora",
            str(dataset_path),
        ],
    )

    assert result.exit_code == 0
    assert calls["upload"] == 1
    assert calls["suffix"] == "lote-42"
    assert calls["metadata"]["project"] == "egregora"
    assert calls["dry_run"] is False
    assert calls["enabled"] is True


def test_generate_cli_archive_skips_when_dry_run(monkeypatch, tmp_path: Path) -> None:
    data = {
        "date": [date(2025, 1, 1)],
        "time": ["09:00"],
        "anon_author": ["Member-AAAA"],
        "message": ["Mensagem"],
        "group_name": ["Grupo"],
        "group_slug": ["grupo"],
    }
    frame = pl.DataFrame(data)
    dataset_path = tmp_path / "dataset.parquet"
    frame.write_parquet(dataset_path)

    monkeypatch.setattr(
        "egregora.generate.core.PostGenerator.generate",
        lambda self, source, context: "Conteúdo",
    )

    constructed = {"count": 0}

    class _StubArchiveManager:
        def __init__(self, *_args, **_kwargs) -> None:
            constructed["count"] += 1

    monkeypatch.setattr("egregora.generate.cli.ArchiveManager", _StubArchiveManager)

    runner = CliRunner()
    result = runner.invoke(
        generate_app,
        ["--archive", "--dry-run", str(dataset_path)],
    )

    assert result.exit_code == 0
    assert constructed["count"] == 0


def test_generate_cli_archive_failure_reports_error(monkeypatch, tmp_path: Path) -> None:
    data = {
        "date": [date(2025, 1, 1)],
        "time": ["09:00"],
        "anon_author": ["Member-AAAA"],
        "message": ["Mensagem"],
        "group_name": ["Grupo"],
        "group_slug": ["grupo"],
    }
    frame = pl.DataFrame(data)
    dataset_path = tmp_path / "dataset.parquet"
    frame.write_parquet(dataset_path)

    monkeypatch.setattr(
        "egregora.generate.core.PostGenerator.generate",
        lambda self, source, context: "Conteúdo",
    )

    class _Builder:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def sync_posts(self, *_args, **_kwargs):
            return []

        @property
        def destination_dir(self) -> Path:
            return dataset_path.parent

        def build_site(self) -> None:
            return None

        def serve_site(self) -> None:
            return None

    monkeypatch.setattr("egregora.generate.cli.StaticSiteBuilder", _Builder)

    class _FailingArchiveManager:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def upload_dataset(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            raise ArchiveUploadError("falha simulada")

    monkeypatch.setattr("egregora.generate.cli.ArchiveManager", _FailingArchiveManager)

    runner = CliRunner()
    result = runner.invoke(generate_app, ["--archive", str(dataset_path)])

    assert result.exit_code == 1
    assert "Falha ao arquivar dataset" in result.stdout
