import zipfile
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import re
from ..core.models import Message
from ..parser import parse_export
from ..models import WhatsAppExport
from ..types import GroupSlug


def load_messages_from_zip(zip_path: Path) -> dict[str, list[Message]]:
    """Load messages from WhatsApp export and group by date."""

    group_name, chat_file = _discover_chat_file(zip_path)
    group_slug = GroupSlug(_slugify(group_name))

    export = WhatsAppExport(
        zip_path=zip_path,
        group_name=group_name,
        group_slug=group_slug,
        export_date=datetime.now().date(),
        chat_file=chat_file,
        media_files=[],
    )

    df = parse_export(export)

    messages_by_date = defaultdict(list)

    for row in df.iter_rows(named=True):
        msg = Message(
            id=f"{row['timestamp'].isoformat()}_{row.get('author', 'system')}",
            timestamp=row["timestamp"],
            author=row.get("author", "system"),
            content=row.get("message", ""),
            media_files=[],
            metadata={},
        )

        date_key = row["timestamp"].strftime("%Y-%m-%d")
        messages_by_date[date_key].append(msg)

    return dict(messages_by_date)


def _discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in the ZIP and extract group name."""

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith(".txt") and not member.startswith("__"):
                group_name = _extract_group_name(member)
                return group_name, member

    raise ValueError(f"No WhatsApp chat file found in {zip_path}")


def _extract_group_name(filename: str) -> str:
    """Extract group name from chat filename."""

    patterns = [
        r"Conversa do WhatsApp com (.+)\.txt",
        r"WhatsApp Chat with (.+)\.txt",
        r"Chat de WhatsApp con (.+)\.txt",
    ]

    for pattern in patterns:
        match = re.match(pattern, Path(filename).name)
        if match:
            return match.group(1)

    return Path(filename).stem


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""

    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')
