"""WhatsApp-specific data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from egregora.sources.base import Export
from egregora.types import GroupSlug


@dataclass(slots=True)
class WhatsAppExport(Export):
    """Metadata extracted from a WhatsApp ZIP export."""

    zip_path: Path
    group_name: str  # "RC LatAm"
    group_slug: GroupSlug  # "rc-latam"
    export_date: date  # 2025-10-01
    chat_file: str  # "Conversa do WhatsApp com RC LatAm.txt"
    # Full paths of the media files within the ZIP archive
    media_files: list[str]  # ["IMG-001.jpg", ...]
