"""Internet Archive integration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import shutil

import internetarchive

from ..config import PipelineConfig


class ArchiveError(RuntimeError):
    """Base exception for archival operations."""


class ArchiveUploadError(ArchiveError):
    """Raised when uploading to the Internet Archive fails."""


class ArchiveDownloadError(ArchiveError):
    """Raised when downloading from the Internet Archive fails."""


class ArchiveNotFoundError(ArchiveError):
    """Raised when no dataset could be located for download."""


@dataclass(slots=True)
class ArchiveUploadResult:
    """Metadata describing an upload attempt."""

    identifier: str
    source: Path
    local_copy: Path | None
    metadata: Mapping[str, str]
    dry_run: bool


@dataclass(slots=True)
class ArchiveDownloadResult:
    """Metadata describing a download operation."""

    identifier: str
    destination: Path
    files: list[Path]
    dry_run: bool


class ArchiveManager:
    """Manage uploads and downloads with the Internet Archive."""

    def __init__(
        self,
        config: PipelineConfig,
        *,
        upload_func: Any | None = None,
        search_func: Any | None = None,
        download_func: Any | None = None,
    ) -> None:
        self.config = config
        self._upload = upload_func or internetarchive.upload
        self._search_items = search_func or internetarchive.search_items
        self._download = download_func or internetarchive.download

    def build_identifier(
        self,
        *,
        timestamp: datetime | None = None,
        suffix: str | None = None,
    ) -> str:
        base = self.config.archive.ia_identifier
        marker = (timestamp or datetime.now(UTC)).strftime("%Y%m%d")
        parts: list[str] = [base, marker]
        if suffix:
            safe = "-".join(part for part in _sanitize_suffix(suffix).split("-") if part)
            if safe:
                parts.append(safe)
        return "-".join(parts)

    def upload_dataset(
        self,
        parquet_path: Path,
        *,
        identifier: str | None = None,
        suffix: str | None = None,
        metadata: Mapping[str, str] | None = None,
        dry_run: bool = False,
    ) -> ArchiveUploadResult:
        if not parquet_path.exists():
            raise ArchiveUploadError(f"Arquivo inexistente: {parquet_path}")
        if parquet_path.suffix.lower() != ".parquet":
            raise ArchiveUploadError("Apenas arquivos Parquet podem ser arquivados.")

        resolved_identifier = identifier or self.build_identifier(suffix=suffix)
        dataset_dir = self.config.archive.dataset_dir
        dataset_dir.mkdir(parents=True, exist_ok=True)

        local_copy: Path | None = None
        payload_metadata = self._compose_metadata(resolved_identifier, metadata)

        if dry_run or not self.config.archive.enabled:
            return ArchiveUploadResult(
                identifier=resolved_identifier,
                source=parquet_path,
                local_copy=None,
                metadata=payload_metadata,
                dry_run=True,
            )

        local_copy = dataset_dir / f"{resolved_identifier}{parquet_path.suffix}"
        shutil.copy2(parquet_path, local_copy)

        response = self._upload(
            resolved_identifier,
            files=[str(local_copy)],
            metadata=dict(payload_metadata),
            verbose=False,
        )

        if not _responses_successful(response):
            raise ArchiveUploadError(
                f"Falha ao enviar {parquet_path} para o Internet Archive (item {resolved_identifier})."
            )

        return ArchiveUploadResult(
            identifier=resolved_identifier,
            source=parquet_path,
            local_copy=local_copy,
            metadata=payload_metadata,
            dry_run=False,
        )

    def find_latest_identifier(self) -> str | None:
        query = f"identifier:{self.config.archive.ia_identifier}-*"
        try:
            results = self._search_items(
                query,
                params={"sort[]": "addeddate desc", "fields": "identifier"},
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise ArchiveDownloadError(f"Falha ao consultar Internet Archive: {exc}") from exc

        for entry in results:
            identifier = entry.get("identifier") if isinstance(entry, Mapping) else None
            if identifier:
                return str(identifier)
        return None

    def download_identifier(
        self,
        identifier: str,
        destination: Path | None = None,
        *,
        dry_run: bool = False,
    ) -> ArchiveDownloadResult:
        target_dir = destination or self.config.archive.dataset_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        if dry_run:
            return ArchiveDownloadResult(
                identifier=identifier,
                destination=target_dir,
                files=[],
                dry_run=True,
            )

        response = self._download(
            identifier,
            destdir=str(target_dir),
            verbose=False,
            ignore_existing=True,
            return_responses=True,
        )

        if not _responses_successful(response):
            raise ArchiveDownloadError(f"Falha ao baixar item {identifier} do Internet Archive.")

        files = self._collect_downloaded_files(target_dir, identifier)
        return ArchiveDownloadResult(
            identifier=identifier,
            destination=target_dir,
            files=files,
            dry_run=False,
        )

    def download_latest(
        self,
        destination: Path | None = None,
        *,
        dry_run: bool = False,
    ) -> ArchiveDownloadResult:
        identifier = self.find_latest_identifier()
        if not identifier:
            raise ArchiveNotFoundError(
                f"Nenhum dataset encontrado com prefixo '{self.config.archive.ia_identifier}'."
            )
        return self.download_identifier(identifier, destination=destination, dry_run=dry_run)

    def _compose_metadata(
        self,
        identifier: str,
        extra: Mapping[str, str] | None,
    ) -> dict[str, str]:
        today = datetime.now(UTC).date().isoformat()
        payload = {
            "title": f"Egregora vectors {identifier}",
            "mediatype": "data",
            "collection": "opensource",
            "subject": "egregora;whatsapp;embeddings",
            "date": today,
            "description": "Embeddings gerados pela pipeline local-first do Egregora.",
        }
        if extra:
            payload.update({str(key): str(value) for key, value in extra.items()})
        return payload

    def _collect_downloaded_files(self, destination: Path, identifier: str) -> list[Path]:
        base_dir = destination / identifier
        collected: list[Path] = []
        if base_dir.exists():
            collected.extend(path for path in base_dir.rglob("*") if path.is_file())
        else:
            collected.extend(path for path in destination.glob(f"{identifier}*.parquet") if path.is_file())
            collected.extend(path for path in destination.glob(f"{identifier}*.json") if path.is_file())
        return collected


def _responses_successful(response: Any) -> bool:
    if response is None:
        return False

    if isinstance(response, Sequence) and not isinstance(response, (str, bytes)):
        items = list(response)
    else:
        items = [response]

    if not items:
        return True

    for item in items:
        if isinstance(item, Mapping):
            status = str(item.get("status", "success")).lower()
            if status not in {"success", "ok"}:
                return False
            continue
        status_code = getattr(item, "status_code", None)
        if status_code is not None and int(status_code) >= 400:
            return False
        status_text = getattr(item, "status", None)
        if isinstance(status_text, str) and status_text.lower() not in {"success", "ok"}:
            return False
    return True


def _sanitize_suffix(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.lower())


__all__ = [
    "ArchiveDownloadError",
    "ArchiveDownloadResult",
    "ArchiveError",
    "ArchiveManager",
    "ArchiveNotFoundError",
    "ArchiveUploadError",
    "ArchiveUploadResult",
]
