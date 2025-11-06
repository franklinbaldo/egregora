"""WhatsApp-specific data models."""

from __future__ import annotations
from dataclasses import dataclass
from egregora.sources.base import Export


@dataclass(slots=True)
class WhatsAppExport(Export):
    """Metadata extracted from a WhatsApp ZIP export.

    Inherits all fields from the base Export class:
    - zip_path: Path to the ZIP file
    - group_name: Display name (e.g., "RC LatAm")
    - group_slug: URL-safe slug (e.g., "rc-latam")
    - export_date: Date of export (e.g., 2025-10-01)
    - chat_file: Name of chat file in ZIP (e.g., "Conversa do WhatsApp com RC LatAm.txt")
    - media_files: List of media file paths in ZIP (e.g., ["IMG-001.jpg", ...])

    This class doesn't add WhatsApp-specific fields but exists to maintain
    type distinction and potential future extension.
    """
