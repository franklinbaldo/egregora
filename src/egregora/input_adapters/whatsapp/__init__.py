"""WhatsApp source adapter package."""

from egregora.input_adapters.whatsapp.adapter import DeliverMediaKwargs, WhatsAppAdapter
from egregora.input_adapters.whatsapp.commands import (
    EGREGORA_COMMAND_PATTERN,
    extract_commands,
    filter_egregora_messages,
)
from egregora.input_adapters.whatsapp.parsing import WhatsAppExport, parse_source
from egregora.input_adapters.whatsapp.utils import (
    build_message_attrs,
    convert_media_to_markdown,
    discover_chat_file,
    normalize_media_markdown,
)

__all__ = [
    "EGREGORA_COMMAND_PATTERN",
    "DeliverMediaKwargs",
    "WhatsAppAdapter",
    "WhatsAppExport",
    "build_message_attrs",
    "convert_media_to_markdown",
    "discover_chat_file",
    "extract_commands",
    "filter_egregora_messages",
    "normalize_media_markdown",
    "parse_source",
]
