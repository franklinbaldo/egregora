from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

def process_whatsapp_export(
    zip_path: Path,
    output_dir: Path,
    gemini_api_key: str,
    period: str,
    enable_enrichment: bool,
    from_date: date | None,
    to_date: date | None,
    timezone: Any,
    model: str | None,
    retrieval_mode: str,
    retrieval_nprobe: int | None,
    retrieval_overfetch: int | None,
) -> None: ...
