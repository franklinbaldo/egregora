"""Tests for WhatsApp export date discovery helpers."""

from __future__ import annotations

import os
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from egregora.group_discovery import _extract_date


CHAT_FILE = "Conversa do WhatsApp com Test.txt"


def _create_zip(tmp_path, filename: str, *, content: str) -> tuple[str, Path]:
    zip_path = tmp_path / filename
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(CHAT_FILE, content)
    return CHAT_FILE, zip_path


def test_extract_date_from_filename(tmp_path):
    chat_file, zip_path = _create_zip(
        tmp_path,
        "chat2025-10-03.zip",
        content="No date content here",
    )

    with zipfile.ZipFile(zip_path) as zf:
        extracted_date = _extract_date(zip_path, zf, chat_file)

    assert extracted_date == date(2025, 10, 3)


def test_extract_date_from_content(tmp_path):
    chat_file, zip_path = _create_zip(
        tmp_path,
        "chat-natural-name.zip",
        content="03/10/2025 09:45 - Test message",
    )

    with zipfile.ZipFile(zip_path) as zf:
        extracted_date = _extract_date(zip_path, zf, chat_file)

    assert extracted_date == date(2025, 10, 3)


def test_future_date_falls_back_to_mtime(tmp_path):
    future_date = date.today() + timedelta(days=30)
    chat_file, zip_path = _create_zip(
        tmp_path,
        f"chat-{future_date.isoformat()}.zip",
        content="No date content here",
    )

    mtime = datetime(2021, 5, 4, 12, 30)
    os.utime(zip_path, (mtime.timestamp(), mtime.timestamp()))

    with zipfile.ZipFile(zip_path) as zf:
        extracted_date = _extract_date(zip_path, zf, chat_file)

    assert extracted_date == mtime.date()
