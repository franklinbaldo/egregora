from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List

from .types import GroupSlug

@dataclass(slots=True)
class WhatsAppExport:
    zip_path: Path
    group_name: str
    group_slug: GroupSlug
    export_date: date
    chat_file: str
    media_files: List[str]
