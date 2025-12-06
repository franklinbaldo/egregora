"""Shared utilities for the WhatsApp adapter."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import ibis
import ibis.expr.datatypes as dt

from egregora.ops.media import ATTACHMENT_MARKERS, WA_MEDIA_PATTERN, detect_media_type
from egregora.utils.zip import validate_zip_contents

_CHW_PATTERN_RAW = r"WhatsApp(?: Chat with|.*) (.+)\.txt"
_CHAT_FILE_PATTERN = re.compile(_CHW_PATTERN_RAW)


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in zip_path and infer the group name."""
    with zipfile.ZipFile(zip_path) as zf:
        validate_zip_contents(zf)
        candidates: list[tuple[int, str, str]] = []
        for member in zf.namelist():
            if not member.endswith(".txt") or member.startswith("__"):
                continue

            match = _CHAT_FILE_PATTERN.match(Path(member).name)
            file_info = zf.getinfo(member)
            score = file_info.file_size
            if match:
                score += 1_000_000
                group_name = match.group(1)
            else:
                group_name = Path(member).stem
            candidates.append((score, group_name, member))

        if not candidates:
            msg = f"No WhatsApp chat file found in {zip_path}"
            raise ValueError(msg)

        candidates.sort(reverse=True, key=lambda item: item[0])
        _, group_name, member = candidates[0]
        return (group_name, member)


def _convert_whatsapp_media_to_markdown(message: str) -> str:
    """Convert WhatsApp media references to markdown format."""
    if not message:
        return message
    result = message
    media_files = WA_MEDIA_PATTERN.findall(message)
    for filename in media_files:
        media_type = detect_media_type(Path(filename)) or "file"
        if media_type == "image":
            markdown = f"![Image]({filename})"
        elif media_type == "video":
            markdown = f"[Video]({filename})"
        elif media_type == "audio":
            markdown = f"[Audio]({filename})"
        elif media_type == "document":
            markdown = f"[Document]({filename})"
        else:
            markdown = f"[File]({filename})"
        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(filename) + "\\s*" + re.escape(marker)
            result = re.sub(pattern, markdown, result, flags=re.IGNORECASE)
        if filename in result and markdown not in result:
            result = re.sub("\\b" + re.escape(filename) + "\\b", markdown, result)
    return result


def build_message_attrs(
    original_line: ibis.Expr,
    tagged_line: ibis.Expr,
    message_date: ibis.Expr,
) -> ibis.Expr:
    """Return message metadata serialized as JSON when any field is present."""
    attrs_struct = ibis.struct(
        {
            "original_line": original_line,
            "tagged_line": tagged_line,
            "message_date": message_date,
        }
    )
    has_metadata = ibis.coalesce(original_line, tagged_line, message_date).notnull()
    attrs_json = attrs_struct.cast(dt.json).cast(dt.string)
    empty_json = ibis.literal(None, type=dt.string)
    return ibis.cases((has_metadata, attrs_json), else_=empty_json)


def convert_media_to_markdown(message: str | None) -> str | None:
    """Convert media references to markdown, returning None for missing values."""
    if message is None:
        return None
    return _convert_whatsapp_media_to_markdown(message)


def normalize_media_markdown(messages: ibis.Table) -> ibis.Table:
    """Normalize WhatsApp media references in a table of messages."""

    @ibis.udf.scalar.python
    def convert_media(message: str | None) -> str | None:
        return convert_media_to_markdown(message)

    return messages.mutate(text=convert_media(messages.text))


__all__ = [
    "build_message_attrs",
    "convert_media_to_markdown",
    "discover_chat_file",
    "normalize_media_markdown",
]
