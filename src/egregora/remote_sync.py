"""Shared helpers for synchronising remote WhatsApp exports."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .config import PipelineConfig
from .remote_source import RemoteSourceError, sync_remote_zips

__all__ = ["RemoteSyncOutcome", "sync_remote_source_config"]


@dataclass(slots=True)
class RemoteSyncOutcome:
    """Outcome information for a remote synchronisation attempt."""

    attempted: bool
    new_archives: list[Path]
    all_archives: list[Path]
    error: RemoteSourceError | None = None

    @property
    def success(self) -> bool:
        """Return ``True`` when the synchronisation completed without errors."""

        return self.attempted and self.error is None


def sync_remote_source_config(
    config: PipelineConfig, *, logger: logging.Logger | None = None
) -> RemoteSyncOutcome:
    """Synchronise remote exports as configured by :class:`PipelineConfig`."""

    url = config.remote_source.get_gdrive_url()
    if not url:
        return RemoteSyncOutcome(False, [], [])

    target_dir = config.zips_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    before = {path.resolve() for path in target_dir.rglob("*.zip")}

    try:
        sync_remote_zips(url, target_dir, logger=logger)
    except RemoteSourceError as exc:
        return RemoteSyncOutcome(True, [], sorted(before), error=exc)

    after = {path.resolve() for path in target_dir.rglob("*.zip")}
    new_paths = sorted(after - before)

    return RemoteSyncOutcome(True, new_paths, sorted(after))
