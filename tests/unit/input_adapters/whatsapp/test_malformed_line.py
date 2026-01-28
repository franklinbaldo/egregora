import zipfile
from datetime import date
from pathlib import Path

import pytest

from egregora.input_adapters.whatsapp.parsing import (
    MalformedLineError,
    WhatsAppExport,
    parse_source,
)


def test_parse_source_raises_malformed_line_error(tmp_path: Path):
    """Verify parse_source raises MalformedLineError for a malformed line in a valid chat."""
    zip_path = tmp_path / "whatsapp_malformed.zip"
    chat_file_name = "_chat.txt"
    chat_content = (
        "1/1/22, 12:00 - User 1: Hello\n"
        "99/99/99, 12:01 - User 2: This date is malformed\n"
        "1/1/22, 12:02 - User 3: World\n"
    )

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(chat_file_name, chat_content)

    mock_export = WhatsAppExport(
        zip_path=zip_path,
        group_name="Test Group",
        group_slug="test-group",
        export_date=date(2022, 1, 1),
        chat_file=chat_file_name,
        media_files=[],
    )

    with pytest.raises(MalformedLineError):
        parse_source(mock_export, timezone="UTC")
