from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
@dataclass
class ProcessConfig:
    zip_file: Path
    output_dir: Path
    period: str
    enable_enrichment: bool
    from_date: date | None
    to_date: date | None
    timezone: str | None
    gemini_key: str | None
    model: str | None
    debug: bool
    retrieval_mode: str
    retrieval_nprobe: int | None
    retrieval_overfetch: int | None

@dataclass
class RankingCliConfig:
    site_dir: Path
    comparisons: int
    strategy: str
    export_parquet: bool
    model: str | None
    debug: bool
