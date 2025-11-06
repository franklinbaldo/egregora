"""Base classes for platform-specific sources."""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path
    from egregora.types import GroupSlug


@dataclass(slots=True)
class Export:
    """Base class for chat export metadata.

    Platform-specific implementations (WhatsApp, Slack, Discord, etc.)
    should inherit from this class and add their specific fields.
    """

    zip_path: Path
    group_name: str
    group_slug: GroupSlug
    export_date: date
    chat_file: str
    media_files: list[str]
