import io
import uuid
import zipfile
from datetime import date, datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo
import pytest
from unittest.mock import MagicMock, Mock, patch

from egregora.input_adapters.whatsapp.parsing import (
    scrub_pii,
    anonymize_author,
    _normalize_text,
    _parse_message_date,
    _parse_message_time,
    MessageBuilder,
    ZipMessageSource,
    parse_source,
    WhatsAppExport,
    MalformedLineError,
    NoMessagesFoundError,
    ZipValidationError,
)
from egregora.config.settings import EgregoraConfig, PrivacySettings
from egregora.input_adapters.whatsapp.exceptions import DateParsingError, TimeParsingError

# Helpers
def create_mock_export(zip_path="dummy.zip", chat_file="chat.txt"):
    return WhatsAppExport(
        zip_path=zip_path,
        group_name="test_group",
        group_slug="test-group",
        export_date=date(2023, 1, 1),
        chat_file=chat_file,
        media_files=[]
    )

class TestParsingUtilities:

    def test_scrub_pii(self):
        text = "Contact me at user@example.com or +1 555 123 4567."
        scrubbed = scrub_pii(text)
        assert "<EMAIL_REDACTED>" in scrubbed
        assert "<PHONE_REDACTED>" in scrubbed
        assert "user@example.com" not in scrubbed
        assert "+1 555 123 4567" not in scrubbed

    def test_scrub_pii_disabled_via_config(self):
        config = Mock(spec=EgregoraConfig)
        config.privacy = Mock(spec=PrivacySettings)
        config.privacy.pii_detection_enabled = False

        text = "user@example.com"
        assert scrub_pii(text, config) == text

    def test_anonymize_author(self):
        ns = uuid.uuid4()
        author = "John Doe"
        uuid_str = anonymize_author(author, ns)
        # Should be deterministic
        assert uuid_str == anonymize_author(author, ns)
        # Should be UUID string
        assert uuid.UUID(uuid_str)

    def test_normalize_text(self):
        # Test invisible marks removal
        text_with_mark = "Hello\u200eWorld"
        assert _normalize_text(text_with_mark) == "HelloWorld"

        # Test HTML escaping
        text_html = "<script>alert(1)</script>"
        assert _normalize_text(text_html) == "&lt;script&gt;alert(1)&lt;/script&gt;"

    def test_parse_message_date(self):
        assert _parse_message_date("01/02/23") == date(2023, 2, 1) # Assuming dd/mm/yy based on order preference
        assert _parse_message_date("2023-01-31") == date(2023, 1, 31)

        with pytest.raises(DateParsingError):
            _parse_message_date("invalid-date")

        with pytest.raises(DateParsingError):
            _parse_message_date("")

    def test_parse_message_time(self):
        assert _parse_message_time("14:30") == time(14, 30)
        assert _parse_message_time("2:30 PM") == time(14, 30)
        assert _parse_message_time("2:30 AM") == time(2, 30)
        assert _parse_message_time("12:30 PM") == time(12, 30)
        assert _parse_message_time("12:30 AM") == time(0, 30)

        with pytest.raises(TimeParsingError):
            _parse_message_time("invalid-time")

        with pytest.raises(TimeParsingError):
            _parse_message_time("")

        # Test AM/PM malformed
        with pytest.raises(TimeParsingError):
            _parse_message_time("XX:YY PM")


class TestMessageBuilder:
    def test_append_line_without_start(self):
        builder = MessageBuilder(
            tenant_id="test",
            source_identifier="whatsapp",
            current_date=date(2023, 1, 1),
            timezone=ZoneInfo("UTC")
        )
        # Should not raise error
        builder.append_line("orphan line", "orphan line")
        builder.flush()
        assert len(builder.get_rows()) == 0

    def test_message_builder_lifecycle(self):
        builder = MessageBuilder(
            tenant_id="test",
            source_identifier="whatsapp",
            current_date=date(2023, 1, 1),
            timezone=ZoneInfo("UTC")
        )

        ts = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
        builder.start_new_message(ts, "Author", "Hello")
        builder.append_line("World", "World")
        builder.flush()

        rows = builder.get_rows()
        assert len(rows) == 1
        msg = rows[0]
        assert msg["text"] == "Hello\nWorld"
        assert msg["author"] == "Author"
        assert msg["author_uuid"] is not None

class TestZipMessageSource:
    @pytest.fixture
    def mock_zip_file(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("_chat.txt", "line1\nline2")
        return buffer.getvalue()

    def test_lines_iterator(self, mock_zip_file):
        export = create_mock_export(zip_path="dummy.zip", chat_file="_chat.txt")
        source = ZipMessageSource(export)

        with patch("zipfile.ZipFile") as mock_zf_cls:
            mock_zf = MagicMock()
            mock_zf_cls.return_value.__enter__.return_value = mock_zf

            # Mock validation calls
            mock_info = Mock()
            mock_info.file_size = 100
            mock_info.compress_size = 50
            mock_info.filename = "_chat.txt"
            mock_zf.getinfo.return_value = mock_info
            mock_zf.infolist.return_value = [mock_info]

            # Mock open
            mock_zf.open.return_value.__enter__.return_value = io.BytesIO(b"line1\nline2")

            lines = list(source.lines())
            assert lines == ["line1", "line2"]

    def test_lines_decoding_error(self):
        export = create_mock_export(chat_file="_chat.txt")
        source = ZipMessageSource(export)

        with patch("zipfile.ZipFile") as mock_zf_cls:
            mock_zf = MagicMock()
            mock_zf_cls.return_value.__enter__.return_value = mock_zf

            # Mock validation calls
            mock_info = Mock()
            mock_info.file_size = 100
            mock_info.compress_size = 50
            mock_info.filename = "_chat.txt"
            mock_zf.getinfo.return_value = mock_info
            mock_zf.infolist.return_value = [mock_info]

            # Mock open returning bad bytes
            mock_zf.open.return_value.__enter__.return_value = io.BytesIO(b"\xff\xff")

            with pytest.raises(ZipValidationError):
                list(source.lines())

class TestParseSource:
    def test_parse_simple_chat(self):
        lines = [
            "01/01/23, 10:00 - Alice: Hello",
            "01/01/23, 10:01 - Bob: Hi there",
            "How are you?",
        ]
        content = "\n".join(lines)

        export = create_mock_export(chat_file="_chat.txt")

        with patch("egregora.input_adapters.whatsapp.parsing.ZipMessageSource") as MockSource:
            instance = MockSource.return_value
            instance.lines.return_value = iter(lines)

            table = parse_source(export, expose_raw_author=True)
            rows = table.to_pandas()

            assert len(rows) == 2
            assert "Hello" in rows.iloc[0]["text"]
            assert "Hi there\nHow are you?" in rows.iloc[1]["text"]
            assert rows.iloc[0]["author_raw"] == "Alice"

    def test_parse_no_messages(self):
        export = create_mock_export()
        with patch("egregora.input_adapters.whatsapp.parsing.ZipMessageSource") as MockSource:
            instance = MockSource.return_value
            instance.lines.return_value = iter([])

            with pytest.raises(NoMessagesFoundError):
                parse_source(export)

    def test_malformed_line(self):
        bad_lines = ["99/99/23, 10:00 - Alice: Hello"]

        export = create_mock_export()
        with patch("egregora.input_adapters.whatsapp.parsing.ZipMessageSource") as MockSource:
            instance = MockSource.return_value
            instance.lines.return_value = iter(bad_lines)

            with pytest.raises(MalformedLineError):
                parse_source(export)
