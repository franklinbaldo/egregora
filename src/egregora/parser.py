"""WhatsApp chat parser that converts ZIP exports to Polars DataFrames."""

from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import datetime
from typing import Iterable

import polars as pl

from .date_utils import parse_flexible_date
from .models import WhatsAppExport
from .zip_utils import ZipValidationError, ensure_safe_member_size, validate_zip_contents

logger = logging.getLogger(__name__)


def parse_export(export: WhatsAppExport) -> pl.DataFrame:
    """Parse an individual export into a Polars ``DataFrame``."""

    with zipfile.ZipFile(export.zip_path) as zf:
        validate_zip_contents(zf)
        ensure_safe_member_size(zf, export.chat_file)

        try:
            with zf.open(export.chat_file) as raw:
                text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
                rows = _parse_messages(text_stream, export)
        except UnicodeDecodeError as exc:
            raise ZipValidationError(
                f"Failed to decode chat file '{export.chat_file}': {exc}"
            ) from exc

    if not rows:
        logger.warning("No messages found in %s", export.zip_path)
        return pl.DataFrame()

    return pl.DataFrame(rows).sort("timestamp")


def parse_multiple(exports: list[WhatsAppExport]) -> pl.DataFrame:
    """Parse multiple exports and concatenate them ordered by timestamp."""

    frames: list[pl.DataFrame] = []

    for export in exports:
        try:
            df = parse_export(export)
        except ZipValidationError as exc:
            logger.warning("Skipping %s due to unsafe ZIP: %s", export.zip_path.name, exc)
            continue
        if not df.is_empty():
            frames.append(df)

    if not frames:
        return pl.DataFrame()

    return pl.concat(frames).sort("timestamp")


_LINE_PATTERN = re.compile(
    r"^(?:"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})"
    r"(?:,\s*|\s+)"
    r")?"
    r"(?P<time>\d{1,2}:\d{2})"
    r"(?:\s*(?P<ampm>[APap][Mm]))?"
    r"\s*[—\-]\s*"
    r"(?P<author>[^:]+?):\s*"
    r"(?P<message>.+)$"
)


def _parse_messages(lines: Iterable[str], export: WhatsAppExport) -> list[dict]:
    """Parse messages from an iterable of strings."""

    rows: list[dict] = []
    current_date = export.export_date

    for raw_line in lines:
        line = raw_line.strip().replace("\u202f", " ")
        if not line:
            continue

        match = _LINE_PATTERN.match(line)
        if not match:
            continue

        date_str = match.group("date")
        time_str = match.group("time")
        am_pm = match.group("ampm")
        author = match.group("author")
        message = match.group("message")

        if date_str:
            parsed_date = parse_flexible_date(date_str)
            if parsed_date:
                msg_date = parsed_date
                current_date = parsed_date
            else:
                msg_date = current_date
        else:
            msg_date = current_date

        try:
            if am_pm:
                msg_time = datetime.strptime(
                    f"{time_str} {am_pm.upper()}", "%I:%M %p"
                ).time()
            else:
                msg_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            logger.debug("Failed to parse time '%s' in line: %s", time_str, line)
            continue

        if _is_system_message(author.strip(), message.strip()):
            continue

        rows.append(
            {
                "timestamp": datetime.combine(msg_date, msg_time),
                "date": msg_date,
                "time": msg_time.strftime("%H:%M"),
                "author": author.strip(),
                "message": message.strip(),
                "group_slug": export.group_slug,
                "group_name": export.group_name,
                "original_line": line,
            }
        )

    return rows


def _is_system_message(author: str, message: str) -> bool:
    """Check if this is a WhatsApp system message to skip."""

    system_phrases = [
        "mudou o assunto do grupo",
        "changed the group subject",
        "cambió el asunto del grupo",
        "adicionou",
        "added you",
        "te agregó",
        "saiu",
        "left",
        "salió",
        "criou o grupo",
        "created group",
        "creó el grupo",
        "as mensagens e chamadas",
        "messages and calls",
        "los mensajes y las llamadas",
        "criptografia de ponta a ponta",
        "end-to-end encrypted",
        "cifrado de extremo a extremo",
    ]

    combined_text = f"{author} {message}".casefold()
    return any(phrase in combined_text for phrase in system_phrases)
