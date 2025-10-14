"""Unit tests for the Internet Archive manager."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from egregora.archive.uploader import (
    ArchiveDownloadError,
    ArchiveManager,
    ArchiveNotFoundError,
    ArchiveUploadError,
)
from egregora.config import PipelineConfig


def _workspace() -> Path:
    root = Path("tmp-tests") / f"archive-{uuid4().hex}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _config_for_workspace(root: Path) -> PipelineConfig:
    config = PipelineConfig(posts_dir=root / "posts")
    config.archive.enabled = True
    config.archive.dataset_dir = root / "exports"
    return config


def test_upload_dataset_copies_file_and_calls_api(monkeypatch) -> None:
    workspace = _workspace()
    source = workspace / "vectors.parquet"
    source.write_bytes(b"data")

    config = _config_for_workspace(workspace)

    calls: dict[str, object] = {}

    def _fake_upload(identifier: str, files, metadata, verbose: bool = False):  # noqa: ANN001
        calls["identifier"] = identifier
        calls["files"] = files
        calls["metadata"] = metadata
        return [SimpleNamespace(status_code=200)]

    manager = ArchiveManager(config, upload_func=_fake_upload)
    result = manager.upload_dataset(source, identifier="egregora-vectors-20250101")

    expected_copy = config.archive.dataset_dir / "egregora-vectors-20250101.parquet"
    assert result.local_copy == expected_copy
    assert expected_copy.exists()
    assert calls["identifier"] == "egregora-vectors-20250101"
    assert calls["files"] == [str(expected_copy)]
    assert "title" in calls["metadata"]


def test_upload_dataset_dry_run_skips_copy() -> None:
    workspace = _workspace()
    source = workspace / "vectors.parquet"
    source.write_bytes(b"dry")

    config = _config_for_workspace(workspace)
    manager = ArchiveManager(config)

    result = manager.upload_dataset(source, identifier="egregora-vectors-20250101", dry_run=True)

    assert result.dry_run is True
    assert result.local_copy is None
    assert not any(config.archive.dataset_dir.glob("*.parquet"))


def test_upload_dataset_raises_when_api_fails() -> None:
    workspace = _workspace()
    source = workspace / "vectors.parquet"
    source.write_bytes(b"data")

    config = _config_for_workspace(workspace)

    def _failing_upload(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return [SimpleNamespace(status_code=500)]

    manager = ArchiveManager(config, upload_func=_failing_upload)

    with pytest.raises(ArchiveUploadError):
        manager.upload_dataset(source, identifier="egregora-vectors-20250101")


def test_download_latest_fetches_identifier_and_files(monkeypatch) -> None:
    workspace = _workspace()
    config = _config_for_workspace(workspace)

    def _fake_search(query: str, params):  # noqa: ANN001, ANN202
        assert query.startswith("identifier:egregora-vectors")
        assert "addeddate" in params.get("sort[]", "")
        return [{"identifier": "egregora-vectors-20250101"}]

    def _fake_download(identifier: str, *, destdir: str, **_kwargs):  # noqa: ANN003
        target = Path(destdir) / identifier / "embeddings.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"data")
        return [SimpleNamespace(status_code=200)]

    manager = ArchiveManager(
        config,
        search_func=_fake_search,
        download_func=_fake_download,
    )

    result = manager.download_latest()

    expected = config.archive.dataset_dir / "egregora-vectors-20250101" / "embeddings.parquet"
    assert result.identifier == "egregora-vectors-20250101"
    assert expected.exists()
    assert expected in result.files


def test_download_latest_raises_when_no_results() -> None:
    workspace = _workspace()
    config = _config_for_workspace(workspace)
    manager = ArchiveManager(config, search_func=lambda *_args, **_kwargs: [])

    with pytest.raises(ArchiveNotFoundError):
        manager.download_latest()


def test_download_identifier_propagates_errors() -> None:
    workspace = _workspace()
    config = _config_for_workspace(workspace)

    def _failing_download(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return [SimpleNamespace(status_code=500)]

    manager = ArchiveManager(config, download_func=_failing_download)

    with pytest.raises(ArchiveDownloadError):
        manager.download_identifier("egregora-vectors-20250101")
