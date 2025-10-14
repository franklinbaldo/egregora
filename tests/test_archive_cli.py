"""CLI tests for the archive subcommands."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from typer.testing import CliRunner

from egregora.archive.cli import archive_app
from egregora.archive.uploader import ArchiveDownloadResult, ArchiveUploadResult


def _make_dataset() -> Path:
    root = Path("tmp-tests") / f"archive-cli-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    dataset = root / "vectors.parquet"
    dataset.write_bytes(b"data")
    return dataset


def test_upload_command_reports_dry_run(monkeypatch) -> None:
    dataset = _make_dataset()
    runner = CliRunner()

    def _fake_upload(self, parquet_path: Path, *, identifier=None, suffix=None, metadata=None, dry_run=False):  # noqa: ANN001
        assert dry_run is True
        assert identifier == "egregora-vectors-20250101"
        return ArchiveUploadResult(
            identifier=identifier,
            source=parquet_path,
            local_copy=None,
            metadata=metadata or {},
            dry_run=True,
        )

    monkeypatch.setattr("egregora.archive.cli.ArchiveManager.upload_dataset", _fake_upload)

    result = runner.invoke(
        archive_app,
        [
            "upload",
            str(dataset),
            "--identifier",
            "egregora-vectors-20250101",
            "--dry-run",
            "--meta",
            "project=egregora",
        ],
    )

    assert result.exit_code == 0
    assert "dry-run" in result.stdout.lower()
    assert "egregora-vectors-20250101" in result.stdout


def test_download_command_uses_latest(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_download_latest(self, destination=None, dry_run=False):  # noqa: ANN001
        dest = Path("data/exports")
        return ArchiveDownloadResult(
            identifier="egregora-vectors-20250101",
            destination=dest,
            files=[dest / "egregora-vectors-20250101.parquet"],
            dry_run=dry_run,
        )

    monkeypatch.setattr("egregora.archive.cli.ArchiveManager.download_latest", _fake_download_latest)

    result = runner.invoke(archive_app, ["download", "--latest"])

    assert result.exit_code == 0
    assert "egregora-vectors-20250101" in result.stdout


def test_download_command_requires_identifier_or_latest() -> None:
    runner = CliRunner()
    result = runner.invoke(archive_app, ["download"])
    assert result.exit_code != 0
    combined_output = result.stdout + (result.stderr or "")
    assert "Informe --identifier ou --latest" in combined_output
