from dataclasses import dataclass
from pathlib import Path
from datetime import date


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    # Return simple placeholders for tests
    return "stub-group", "chat.txt"


@dataclass
class WhatsAppExport:
    zip_path: Path
    group_name: str
    group_slug: str
    export_date: date
    chat_file: str
    media_files: list[str] | None = None
