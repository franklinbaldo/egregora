"""Core data models for auto-discovery and virtual groups feature."""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal


@dataclass(slots=True)
class WhatsAppExport:
    """Metadata extracted from a WhatsApp ZIP export."""
    
    zip_path: Path
    group_name: str          # "RC LatAm"
    group_slug: str          # "rc-latam"
    export_date: date        # 2025-10-01
    chat_file: str           # "Conversa do WhatsApp com RC LatAm.txt"
    media_files: list[str]   # ["IMG-001.jpg", ...]


@dataclass(slots=True)
class MergeConfig:
    """Configuration for merging multiple groups into a virtual group."""
    
    name: str                                                    # "RC Americas"
    source_groups: list[str]                                     # ["rc-latam", "rc-brasil"]
    tag_style: Literal["emoji", "brackets", "prefix"] = "emoji"
    group_emojis: dict[str, str] = field(default_factory=dict)   # {"rc-latam": "🌎"}
    model_override: str | None = None


@dataclass(slots=True)
class GroupSource:
    """
    Source for generating newsletters.
    Can be real (single group) or virtual (merge of multiple groups).
    """
    
    slug: str                          # "rc-latam" or "rc-americas"
    name: str                          # "RC LatAm" or "RC Americas"
    exports: list[WhatsAppExport]      # Exports for this source
    is_virtual: bool = False
    merge_config: MergeConfig | None = None