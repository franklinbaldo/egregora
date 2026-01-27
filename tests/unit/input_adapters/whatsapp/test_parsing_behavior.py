"""Behavioral tests for WhatsApp parsing logic."""

<<<<<<< HEAD
from datetime import UTC, date, datetime, time
from unittest.mock import Mock

import pytest

from egregora.input_adapters.whatsapp.parsing import (
    MessageBuilder,
    _normalize_text,
    _parse_message_date,
    _parse_message_time,
    scrub_pii,
=======
import uuid
from datetime import date, datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import Mock

import pytest
from egregora.input_adapters.whatsapp.parsing import (
    scrub_pii,
    _normalize_text,
    _parse_message_date,
    _parse_message_time,
    MessageBuilder,
    anonymize_author,
>>>>>>> origin/pr/2652
)

# --- PII Scrubbing Tests ---

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
def test_scrub_pii_emails():
    """Verify email addresses are redacted."""
    # Given
    text = "Contact me at user@example.com for details."

    # When
    result = scrub_pii(text)

    # Then
    assert "<EMAIL_REDACTED>" in result
    assert "user@example.com" not in result
    assert result == "Contact me at <EMAIL_REDACTED> for details."

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
def test_scrub_pii_phones():
    """Verify phone numbers are redacted."""
    # Given
    text = "Call +1 555 123 4567 or (555) 123-4567."

    # When
    result = scrub_pii(text)

    # Then
    assert result.count("<PHONE_REDACTED>") == 2
    assert "555 123 4567" not in result

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
def test_scrub_pii_config_control():
    """Verify PII scrubbing respects configuration."""
    # Given
    text = "user@example.com"
    config_enabled = Mock(privacy=Mock(pii_detection_enabled=True, scrub_emails=True, scrub_phones=True))
    config_disabled = Mock(privacy=Mock(pii_detection_enabled=False))

    # When
    res_enabled = scrub_pii(text, config_enabled)
    res_disabled = scrub_pii(text, config_disabled)

    # Then
    assert res_enabled == "<EMAIL_REDACTED>"
    assert res_disabled == text

<<<<<<< HEAD

# --- Normalization Tests ---


=======
# --- Normalization Tests ---

>>>>>>> origin/pr/2652
def test_normalize_text_html_escaping():
    """Verify special characters are HTML escaped."""
    # Given
    text = "<script>alert('xss')</script>"

    # When
    result = _normalize_text(text)

    # Then
    assert "&lt;script&gt;" in result
    assert "&lt;/script&gt;" in result

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
def test_normalize_text_invisible_chars():
    """Verify invisible control characters are removed."""
    # Given
    text = "Hello\u200eWorld"  # Left-to-right mark

    # When
    result = _normalize_text(text)

    # Then
    assert result == "HelloWorld"

<<<<<<< HEAD

# --- Date Parsing Tests ---


@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("01/02/23", date(2023, 2, 1)),  # %d/%m/%y (DD/MM/YY)
        ("01/02/2023", date(2023, 2, 1)),  # %d/%m/%Y
        ("2023-02-01", date(2023, 2, 1)),  # %Y-%m-%d
        ("2023/02/01", date(2023, 2, 1)),  # %Y/%m/%d
        ("1.2.23", date(2023, 2, 1)),  # %d.%m.%y
    ],
)
=======
# --- Date Parsing Tests ---

@pytest.mark.parametrize("input_str,expected", [
    ("01/02/23", date(2023, 2, 1)),   # %d/%m/%y (DD/MM/YY)
    ("01/02/2023", date(2023, 2, 1)), # %d/%m/%Y
    ("2023-02-01", date(2023, 2, 1)), # %Y-%m-%d
    ("2023/02/01", date(2023, 2, 1)), # %Y/%m/%d
    ("1.2.23", date(2023, 2, 1)),     # %d.%m.%y
])
>>>>>>> origin/pr/2652
def test_parse_message_date_formats(input_str, expected):
    """Verify various date formats are parsed correctly."""
    assert _parse_message_date(input_str) == expected

<<<<<<< HEAD

# --- Time Parsing Tests ---


@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("13:45", time(13, 45)),
        ("1:45", time(1, 45)),
        ("01:45 PM", time(13, 45)),
        ("1:45 PM", time(13, 45)),
        ("12:00 PM", time(12, 0)),
        ("12:00 AM", time(0, 0)),
        ("11:59 AM", time(11, 59)),
        ("1:45 AM", time(1, 45)),
    ],
)
=======
# --- Time Parsing Tests ---

@pytest.mark.parametrize("input_str,expected", [
    ("13:45", time(13, 45)),
    ("1:45", time(1, 45)),
    ("01:45 PM", time(13, 45)),
    ("1:45 PM", time(13, 45)),
    ("12:00 PM", time(12, 0)),
    ("12:00 AM", time(0, 0)),
    ("11:59 AM", time(11, 59)),
    ("1:45 AM", time(1, 45)),
])
>>>>>>> origin/pr/2652
def test_parse_message_time_formats(input_str, expected):
    """Verify various time formats are parsed correctly."""
    assert _parse_message_time(input_str) == expected

<<<<<<< HEAD

# --- MessageBuilder Tests ---


=======
# --- MessageBuilder Tests ---

>>>>>>> origin/pr/2652
def test_message_builder_multiline():
    """Verify MessageBuilder assembles multi-line messages."""
    # Given
    builder = MessageBuilder(
        tenant_id="test",
        source_identifier="whatsapp",
        current_date=date(2023, 1, 1),
<<<<<<< HEAD
        timezone=UTC,
    )
    ts = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
=======
        timezone=timezone.utc,
    )
    ts = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
>>>>>>> origin/pr/2652

    # When
    builder.start_new_message(ts, "Author", "Line 1")
    builder.append_line("full line 2", "Line 2")
    builder.flush()

    # Then
    rows = builder.get_rows()
    assert len(rows) == 1
    msg = rows[0]
    assert msg["text"] == "Line 1\nLine 2"
    assert msg["author_raw"] == "Author"

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
def test_message_builder_author_anonymization():
    """Verify author anonymization is consistent."""
    # Given
    builder = MessageBuilder(
        tenant_id="test",
        source_identifier="whatsapp",
        current_date=date(2023, 1, 1),
<<<<<<< HEAD
        timezone=UTC,
    )
    ts = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)

    # When
    builder.start_new_message(ts, "Author1", "Msg 1")
    builder.start_new_message(ts, "Author1", "Msg 2")  # Same author
    builder.start_new_message(ts, "Author2", "Msg 3")  # Different author
=======
        timezone=timezone.utc,
    )
    ts = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)

    # When
    builder.start_new_message(ts, "Author1", "Msg 1")
    builder.start_new_message(ts, "Author1", "Msg 2") # Same author
    builder.start_new_message(ts, "Author2", "Msg 3") # Different author
>>>>>>> origin/pr/2652
    builder.flush()

    # Then
    rows = builder.get_rows()
    assert len(rows) == 3
    uuid1 = rows[0]["author_uuid"]
    uuid2 = rows[1]["author_uuid"]
    uuid3 = rows[2]["author_uuid"]

    assert uuid1 == uuid2
    assert uuid1 != uuid3
    assert rows[0]["_author_uuid_hex"] == uuid1.replace("-", "")

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
def test_message_builder_skips_empty_messages():
    """Verify empty messages are skipped."""
    # Given
    builder = MessageBuilder(
        tenant_id="test",
        source_identifier="whatsapp",
        current_date=date(2023, 1, 1),
<<<<<<< HEAD
        timezone=UTC,
    )
    ts = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
=======
        timezone=timezone.utc,
    )
    ts = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
>>>>>>> origin/pr/2652

    # When
    builder.start_new_message(ts, "Author", "")
    builder.flush()

    # Then
    rows = builder.get_rows()
    assert len(rows) == 0
