"""Helpers for synchronising remote WhatsApp exports."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Iterable

import zipfile
import gdown

__all__ = ["RemoteSourceError", "sync_remote_zips"]
class RemoteSourceError(RuntimeError):
    """Raised when synchronising remote ZIP exports fails."""


def _files_match(path_a: Path, path_b: Path) -> bool:
    """Return ``True`` when *path_a* and *path_b* store identical bytes."""

    try:
        if path_a.stat().st_size != path_b.stat().st_size:
            return False
    except OSError:
        return False

    digest_a = hashlib.sha256()
    digest_b = hashlib.sha256()

    try:
        with path_a.open("rb") as handle_a, path_b.open("rb") as handle_b:
            while True:
                chunk_a = handle_a.read(131_072)
                chunk_b = handle_b.read(131_072)
                if not chunk_a and not chunk_b:
                    break
                if chunk_a != chunk_b:
                    return False
                digest_a.update(chunk_a)
                digest_b.update(chunk_b)
    except OSError:
        return False

    return digest_a.digest() == digest_b.digest()


def _ensure_archive_path(path: Path) -> Path | None:
    """Return a path to a valid ZIP archive, normalising missing extensions."""

    if not path.exists() or not path.is_file():
        return None

    suffix = path.suffix.lower()
    if suffix == ".zip":
        return path.resolve()

    try:
        is_zip = zipfile.is_zipfile(path)
    except OSError:
        return None

    if not is_zip:
        return None

    base_name = path.name
    candidate = path.with_name(base_name + ".zip")

    if candidate.exists():
        if _files_match(candidate, path):
            path.unlink(missing_ok=True)
            return candidate.resolve()

        counter = 1
        while candidate.exists():
            if _files_match(candidate, path):
                path.unlink(missing_ok=True)
                return candidate.resolve()
            candidate = path.with_name(f"{base_name}.{counter}.zip")
            counter += 1

    path.rename(candidate)
    return candidate.resolve()


def _normalise_downloaded_paths(paths: Iterable[str], *, target_dir: Path) -> list[Path]:
    """Return existing ZIP files downloaded by gdown.

    ``gdown`` may return relative or absolute paths. This helper normalises the
    paths, ensures a ``.zip`` suffix when needed and filters out invalid files.
    """

    archives: list[Path] = []
    for raw in paths:
        if not raw:
            continue

        candidates = []
        raw_path = Path(raw)
        if raw_path.is_absolute():
            candidates.append(raw_path)
        candidates.append(target_dir / raw)

        archive_path = None
        for candidate in candidates:
            archive_path = _ensure_archive_path(candidate)
            if archive_path is not None:
                break

        if archive_path is not None:
            archives.append(archive_path)

    return archives


def sync_remote_zips(url: str, target_dir: Path, *, logger: logging.Logger | None = None) -> list[Path]:
    """Download WhatsApp ZIP exports from a Google Drive share URL."""

    target_dir = target_dir.expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        if "/folders/" in url:
            files = gdown.download_folder(
                url=url,
                output=str(target_dir),
                quiet=True,
                use_cookies=False,
                remaining_ok=True,
                resume=True,
            )
        else:
            output = gdown.download(
                url=url,
                output=str(target_dir) + "/",
                quiet=True,
                use_cookies=False,
                fuzzy=True,
                resume=True,
            )
            files = [output] if output else []
    except Exception as exc:  # pragma: no cover - defensive around gdown runtime
        raise RemoteSourceError(str(exc)) from exc

    archives = _normalise_downloaded_paths(files or [], target_dir=target_dir)

    archive_set = {archive.resolve() for archive in archives}
    for candidate in target_dir.rglob("*"):
        ensured = _ensure_archive_path(candidate)
        if ensured is not None:
            archive_set.add(ensured)

    archives = sorted(archive_set)

    if logger is not None and archives:
        base = target_dir
        for archive in archives:
            try:
                relative = archive.relative_to(base)
            except ValueError:
                relative = archive
            logger.info("    ↓ %s", relative)

    return archives
