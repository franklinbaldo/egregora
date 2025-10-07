
from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from egregora.remote_source import RemoteSourceError, sync_remote_zips


@pytest.fixture
def target_dir(tmp_path: Path) -> Path:
    path = tmp_path / "zips"
    path.mkdir()
    return path


def test_sync_remote_zips_downloads_folder(monkeypatch: pytest.MonkeyPatch, target_dir: Path) -> None:
    captured: dict[str, object] = {}

    def fake_download_folder(*, url: str, output: str, quiet: bool, use_cookies: bool, remaining_ok: bool, resume: bool, **kwargs):
        captured.update({
            "url": url,
            "output": output,
            "quiet": quiet,
            "use_cookies": use_cookies,
            "remaining_ok": remaining_ok,
            "resume": resume,
        })
        nested = Path(output) / "folder" / "export.zip"
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_bytes(b"data")
        return [str(nested)]

    monkeypatch.setattr(
        "egregora.remote_source.gdown.download_folder",
        fake_download_folder,
    )
    monkeypatch.setattr(
        "egregora.remote_source.gdown.download",
        lambda *args, **kwargs: None,
    )

    url = "https://drive.google.com/drive/folders/abc123"
    downloaded = sync_remote_zips(url, target_dir)

    expected_path = (target_dir / "folder" / "export.zip").resolve()
    assert downloaded == [expected_path]
    assert captured == {
        "url": url,
        "output": str(target_dir),
        "quiet": True,
        "use_cookies": False,
        "remaining_ok": True,
        "resume": True,
    }


def test_sync_remote_zips_downloads_file(monkeypatch: pytest.MonkeyPatch, target_dir: Path) -> None:
    calls: list[tuple[str, str]] = []

    def fake_download(url: str, output: str, quiet: bool, use_cookies: bool, fuzzy: bool, resume: bool, **kwargs):
        calls.append((url, output))
        destination = Path(output.rstrip("/")) / "single.zip"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"content")
        return str(destination)

    monkeypatch.setattr(
        "egregora.remote_source.gdown.download",
        fake_download,
    )
    monkeypatch.setattr(
        "egregora.remote_source.gdown.download_folder",
        lambda *args, **kwargs: [],
    )

    url = "https://drive.google.com/file/d/xyz/view"
    downloaded = sync_remote_zips(url, target_dir)

    dest = (target_dir / "single.zip").resolve()
    assert downloaded == [dest]
    assert calls == [(url, str(target_dir) + "/")]


def test_sync_remote_zips_wraps_errors(monkeypatch: pytest.MonkeyPatch, target_dir: Path) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("failure")

    monkeypatch.setattr(
        "egregora.remote_source.gdown.download_folder",
        boom,
    )

    with pytest.raises(RemoteSourceError) as exc:
        sync_remote_zips("https://drive.google.com/drive/folders/boom", target_dir)

    assert "failure" in str(exc.value)



def test_sync_remote_zips_renames_missing_extension(monkeypatch: pytest.MonkeyPatch, target_dir: Path) -> None:
    def fake_download_folder(*, url: str, output: str, quiet: bool, use_cookies: bool, remaining_ok: bool, resume: bool, **kwargs):
        nested = Path(output) / "folder" / "export"
        nested.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(nested, "w") as zf:
            zf.writestr("dummy.txt", "hello")
        return [str(nested)]

    monkeypatch.setattr(
        "egregora.remote_source.gdown.download_folder",
        fake_download_folder,
    )
    monkeypatch.setattr(
        "egregora.remote_source.gdown.download",
        lambda *args, **kwargs: None,
    )

    url = "https://drive.google.com/drive/folders/rename-me"
    downloaded = sync_remote_zips(url, target_dir)

    expected = (target_dir / "folder" / "export.zip").resolve()
    assert expected in downloaded
    assert expected.exists()
