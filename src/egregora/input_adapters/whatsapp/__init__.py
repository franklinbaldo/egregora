"""WhatsApp source adapter package."""

from .adapter import DeliverMediaKwargs, WhatsAppAdapter
from .commands import EGREGORA_COMMAND_PATTERN, extract_commands, filter_egregora_messages
from .parsing import WhatsAppExport, parse_source
from .utils import build_message_attrs, convert_media_to_markdown, discover_chat_file, normalize_media_markdown

__all__ = [
    "DeliverMediaKwargs",
    "WhatsAppAdapter",
    "EGREGORA_COMMAND_PATTERN",
    "extract_commands",
    "filter_egregora_messages",
    "WhatsAppExport",
    "parse_source",
    "build_message_attrs",
    "convert_media_to_markdown",
    "discover_chat_file",
    "normalize_media_markdown",
]
