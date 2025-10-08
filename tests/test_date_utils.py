from datetime import date
from pathlib import Path

import pytest

from egregora.group_discovery import _parse_preview_date
from egregora.models import WhatsAppExport
from egregora.parser import _parse_message_date, _parse_messages
from egregora.types import GroupSlug


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("01/05/2024", date(2024, 5, 1)),
        ("5/1/2024", date(2024, 1, 5)),
        ("2024-05-01", date(2024, 5, 1)),
    ],
)
def test_date_parsers_accept_multiple_formats(token: str, expected: date) -> None:
    for parser_fn in (_parse_message_date, _parse_preview_date):
        assert parser_fn(token) == expected


def test_date_parsers_normalize_timezones() -> None:
    token = "2024-05-01T00:30:00-03:00"
    for parser_fn in (_parse_message_date, _parse_preview_date):
        assert parser_fn(token) == date(2024, 5, 1)


@pytest.mark.parametrize("token", ["   ", "not a date"])
def test_date_parsers_return_none_for_invalid_tokens(token: str) -> None:
    for parser_fn in (_parse_message_date, _parse_preview_date):
        assert parser_fn(token) is None


def test_parse_messages_updates_contextual_date() -> None:
    export = WhatsAppExport(
        zip_path=Path("dummy.zip"),
        group_name="Test",
        group_slug=GroupSlug("test"),
        export_date=date(2024, 4, 30),
        chat_file="Conversa do WhatsApp com Teste.txt",
        media_files=[],
    )

    lines = [
        "01/05/2024 09:00 - Alice: Bom dia",
        "5/1/2024, 10:30 - Bob: Hello",
        "11:45 - Alice: Sem data explícita usa última conhecida",
    ]

    rows = _parse_messages(lines, export)

    assert [row["date"] for row in rows] == [
        date(2024, 5, 1),
        date(2024, 1, 5),
        date(2024, 1, 5),
    ]
