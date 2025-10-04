"""Utilities to discover pending WhatsApp archives for backlog processing."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List

_URL_RE = re.compile(r"https?://\S+")
_DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclass(slots=True)
class PendingDay:
    """Metadata describing a WhatsApp export day pending processing."""

    date: date
    zip_path: Path
    newsletter_path: Path
    already_processed: bool
    message_count: int
    url_count: int
    participant_count: int


def _count_messages(transcript: str) -> tuple[int, int, int]:
    messages = 0
    urls = 0
    participants: set[str] = set()

    for line in transcript.splitlines():
        if " - " in line and ":" in line:
            try:
                _, remainder = line.split(" - ", 1)
                author, _ = remainder.split(":", 1)
            except ValueError:
                author = ""
            messages += 1
            if author:
                participants.add(author.strip())
        if _URL_RE.search(line):
            urls += len(_URL_RE.findall(line))

    return messages, urls, len(participants)


def _read_zip_texts(zip_path: Path) -> str:
    try:
        with zipfile.ZipFile(zip_path, "r") as zipped:
            txt_names = [name for name in zipped.namelist() if name.lower().endswith(".txt")]
            txt_names.sort()
            chunks: list[str] = []
            for name in txt_names:
                raw = zipped.read(name)
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("latin-1")
                chunks.append(text)
    except (FileNotFoundError, zipfile.BadZipFile):
        return ""

    return "\n".join(chunks)


def _extract_stats(zip_path: Path, archive_date: date) -> tuple[int, int, int]:
    transcript = _read_zip_texts(zip_path)
    if not transcript:
        return 0, 0, 0
    return _count_messages(transcript)


def _find_date_in_name(path: Path) -> date | None:
    match = _DATE_IN_NAME_RE.search(path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def scan_pending_days(zip_dir: Path, output_dir: Path) -> List[PendingDay]:
    """Return a chronologically ordered list of pending days."""

    candidates: list[PendingDay] = []
    for zip_path in sorted(zip_dir.glob("*.zip")):
        archive_date = _find_date_in_name(zip_path)
        if archive_date is None:
            continue

        newsletter_path = output_dir / f"{archive_date.isoformat()}.md"
        processed = newsletter_path.exists()
        message_count, url_count, participant_count = _extract_stats(zip_path, archive_date)

        candidates.append(
            PendingDay(
                date=archive_date,
                zip_path=zip_path,
                newsletter_path=newsletter_path,
                already_processed=processed,
                message_count=message_count,
                url_count=url_count,
                participant_count=participant_count,
            )
        )

    candidates.sort(key=lambda item: item.date)
    return candidates


__all__ = ["PendingDay", "scan_pending_days"]
