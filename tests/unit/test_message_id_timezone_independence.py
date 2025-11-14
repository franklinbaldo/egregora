"""Test that message_id calculation is timezone-independent.

This test verifies that the same WhatsApp conversation exported from
phones in different timezones produces identical message_ids.
"""

import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from egregora.input_adapters.whatsapp.models import WhatsAppExport
from egregora.input_adapters.whatsapp.parser import parse_source


def test_message_id_is_timezone_independent(tmp_path: Path):
    """Verify that message_ids are the same regardless of export timezone.

    This simulates the same WhatsApp conversation exported from two different
    phones in different timezones. The timestamps in the export will differ
    (because WhatsApp uses local time), but the message_ids should be identical
    because we calculate relative deltas, not absolute times.
    """
    # Create two identical conversations with different timezones
    # Simulating the same 3 messages exported from UTC and UTC+5 phones

    # Phone A in UTC timezone
    chat_content_utc = """01/01/2025, 12:00 - Alice: First message
01/01/2025, 12:30 - Bob: Second message
01/01/2025, 13:00 - Alice: Third message"""

    # Phone B in UTC+5 timezone (same real-world time, different local time)
    chat_content_utc5 = """01/01/2025, 17:00 - Alice: First message
01/01/2025, 17:30 - Bob: Second message
01/01/2025, 18:00 - Alice: Third message"""

    # Create export from UTC phone
    export_utc = _create_test_export(tmp_path, "utc_export.zip", chat_content_utc)
    messages_utc = parse_source(export_utc, timezone=ZoneInfo("UTC"))

    # Create export from UTC+5 phone
    export_utc5 = _create_test_export(tmp_path, "utc5_export.zip", chat_content_utc5)
    messages_utc5 = parse_source(export_utc5, timezone=ZoneInfo("Asia/Karachi"))  # UTC+5

    # Convert to pandas for easier comparison
    df_utc = messages_utc.execute()
    df_utc5 = messages_utc5.execute()

    # Verify both have message_id column
    assert "message_id" in df_utc.columns
    assert "message_id" in df_utc5.columns

    # Extract message_ids
    ids_utc = df_utc["message_id"].tolist()
    ids_utc5 = df_utc5["message_id"].tolist()

    # The critical test: message_ids should be IDENTICAL
    # even though the absolute timestamps are 5 hours apart
    assert ids_utc == ids_utc5, (
        f"Message IDs differ between timezones!\n"
        f"UTC export: {ids_utc}\n"
        f"UTC+5 export: {ids_utc5}\n"
        f"This breaks idempotence - same conversation should have same IDs"
    )

    # Verify the deltas make sense
    # Format is "{delta_ms}_{row_num}"
    # First message should be "0_0" (0 ms since start, row 0)
    assert ids_utc[0] == "0_0"
    assert ids_utc5[0] == "0_0"

    # Second message is 30 minutes later = 1800000 milliseconds, row 1
    assert ids_utc[1] == "1800000_1"
    assert ids_utc5[1] == "1800000_1"

    # Third message is 60 minutes later = 3600000 milliseconds, row 2
    assert ids_utc[2] == "3600000_2"
    assert ids_utc5[2] == "3600000_2"


def test_message_id_handles_same_minute_messages(tmp_path: Path):
    """Verify that multiple messages in the same minute get unique IDs.

    WhatsApp exports only have minute-level precision, so multiple messages
    sent in the same minute will have the same timestamp. This test verifies
    that they still get consistent message_ids (all "0" if they're the first
    messages, since we can't distinguish them with minute-level precision).
    """
    # Create a conversation with 3 messages in the same minute
    chat_content = """01/01/2025, 12:00 - Alice: First message
01/01/2025, 12:00 - Bob: Second message in same minute
01/01/2025, 12:00 - Charlie: Third message in same minute
01/01/2025, 12:01 - Alice: Message in next minute"""

    export = _create_test_export(tmp_path, "same_minute.zip", chat_content)
    messages = parse_source(export, timezone=ZoneInfo("UTC"))

    df = messages.execute()
    ids = df["message_id"].tolist()

    # Messages in the same minute (12:00) should have same delta but different row numbers
    # Format: "{delta_ms}_{row_num}"
    assert ids[0] == "0_0", f"First message should be 0_0, got {ids[0]}"
    assert ids[1] == "0_1", f"Second message in same minute should be 0_1, got {ids[1]}"
    assert ids[2] == "0_2", f"Third message in same minute should be 0_2, got {ids[2]}"

    # Message in the next minute (12:01) should be 60000 milliseconds later, row 3
    assert ids[3] == "60000_3", f"Message in next minute should be 60000_3, got {ids[3]}"

    # Verify all IDs are unique (critical for annotations)
    assert len(ids) == len(set(ids)), f"Duplicate message_ids found: {ids}"


def _create_test_export(tmp_path: Path, filename: str, chat_content: str) -> WhatsAppExport:
    """Helper to create a test WhatsApp export ZIP file."""
    zip_path = tmp_path / filename
    chat_filename = "chat.txt"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(chat_filename, chat_content)

    return WhatsAppExport(
        zip_path=zip_path,
        group_name="Test Group",
        group_slug="test-group",
        export_date=datetime(2025, 1, 1).date(),
        chat_file=chat_filename,
        media_files=[],
    )
