from pathlib import Path
from datetime import datetime
from collections import defaultdict
from ..core.models import Message
from ..parser import parse_whatsapp_txt


def load_messages_from_zip(zip_path: Path) -> dict[str, list[Message]]:
    """Load messages from WhatsApp export and group by date."""
    from ..processor import UnifiedProcessor
    from ..config import PipelineConfig

    temp_config = PipelineConfig(zip_files=[zip_path])
    processor = UnifiedProcessor(temp_config)

    all_exports = processor._discover_exports()

    messages_by_date = defaultdict(list)

    for export in all_exports:
        for zip_file in export.exports:
            chat_content = processor._read_chat_file(zip_file.zip_path, zip_file.chat_file)
            parsed = parse_whatsapp_txt(chat_content)

            for entry in parsed:
                msg = Message(
                    id=f"{entry['timestamp'].isoformat()}_{entry.get('author', 'system')}",
                    timestamp=entry["timestamp"],
                    author=entry.get("author", "system"),
                    content=entry.get("message", ""),
                    media_files=entry.get("media", []),
                    metadata=entry.get("metadata", {}),
                )

                date_key = entry["timestamp"].strftime("%Y-%m-%d")
                messages_by_date[date_key].append(msg)

    return dict(messages_by_date)
