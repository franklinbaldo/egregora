"""E2E tests for WhatsApp input adapter.

These tests validate the WhatsApp adapter's ability to parse WhatsApp export
ZIPs into the standardized Interchange Representation (IR).

Tests in this file validate:
- ZIP extraction and validation
- Chat log parsing (dates, authors, messages)
- Media extraction and reference replacement
- Anonymization (UUID5 generation)
- Enrichment transformations
- Schema validation
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import ibis
import pytest

from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.input_adapters.whatsapp import filter_egregora_messages, parse_source
from egregora.utils.zip import ZipValidationError, validate_zip_contents

if TYPE_CHECKING:
    from conftest import WhatsAppFixture


def create_export_from_fixture(fixture: WhatsAppFixture):
    return fixture.create_export()


# Legacy helper placeholder ----------------------------------------------------


def extract_and_replace_media(*_args, **_kwargs):  # pragma: no cover - legacy placeholder
    """Placeholder until legacy media tests are updated to the Document pipeline."""
    message = "Media extraction tests rely on the legacy pipeline"
    raise NotImplementedError(message)


# =============================================================================
# ZIP Extraction & Validation Tests
# =============================================================================


def test_zip_extraction_completes_without_error(whatsapp_fixture: WhatsAppFixture):
    """Test that WhatsApp ZIP is extracted and validated successfully."""
    zip_path = whatsapp_fixture.zip_path
    with zipfile.ZipFile(zip_path) as archive:
        validate_zip_contents(archive)
        members = archive.namelist()

    assert "Conversa do WhatsApp com Teste.txt" in members
    assert sum(1 for member in members if member.endswith(".jpg")) == 4


def test_pipeline_rejects_unsafe_zip(tmp_path: Path):
    """Test that ZIP validation rejects path traversal attempts."""
    malicious_zip = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, "w") as archive:
        archive.writestr("../etc/passwd", "malicious content")

    with (
        pytest.raises(ZipValidationError, match="path traversal"),
        zipfile.ZipFile(malicious_zip) as archive,
    ):
        validate_zip_contents(archive)


# =============================================================================
# Parser Tests (Chat Log → IR Table)
# =============================================================================


@pytest.fixture
def mock_dynamic_regex_fallback(monkeypatch):
    """Mocks the dynamic regex generator to force fallback."""
    monkeypatch.setattr(
        "egregora.input_adapters.whatsapp.parsing.generate_dynamic_regex",
        lambda *args, **kwargs: None,
    )


def test_parser_produces_valid_table(whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback):
    """Test that parser produces valid IR table with expected columns."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    assert set(table.columns) == set(IR_MESSAGE_SCHEMA.names)
    assert table.count().execute() == 10
    messages = table["text"].execute().tolist()
    assert all(message is not None and message.strip() for message in messages)

    timestamps = table["ts"].execute()
    assert all(ts.tzinfo is not None for ts in timestamps)


def test_parser_handles_portuguese_dates(whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback):
    """Test that parser correctly handles Portuguese date formats."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)
    raw_attrs = table["attrs"].execute().tolist()
    attrs = [json.loads(value) if isinstance(value, str) and value else (value or {}) for value in raw_attrs]
    dates = {value.get("message_date") for value in attrs if value}

    assert "2025-10-28" in dates


def test_parser_preserves_all_messages(whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback):
    """Test that parser preserves all participant messages."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    assert table.count().execute() == 10


def test_parser_extracts_media_references(whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback):
    """Test that parser extracts media file references from messages."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    combined = " ".join(table["text"].execute().tolist())
    assert "IMG-20251028-WA0035.jpg" in combined
    assert "arquivo anexado" in combined


def test_parser_enforces_message_schema(whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback):
    """Test that parser strictly enforces IR MESSAGE_SCHEMA without extra columns."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    expected_columns = set(IR_MESSAGE_SCHEMA.names)
    assert set(table.columns) == expected_columns


# =============================================================================
# Anonymization Tests (Author Names → UUIDs)
# =============================================================================


def test_anonymization_removes_real_author_names(
    whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback
):
    """Test that anonymization removes real author names from table."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    authors = table["author_raw"].execute().tolist()
    for forbidden in ("Franklin", "Iuri Brasil", "Você", "Eurico Max"):
        assert forbidden not in authors

    messages = table["text"].execute().tolist()
    assert any("@" in message and "teste de menção" in message for message in messages)


def test_parse_source_exposes_raw_authors_when_requested(
    whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback
):
    """Test that raw author names are exposed when explicitly requested."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(
        export,
        timezone=whatsapp_fixture.timezone,
        expose_raw_author=True,
    )

    authors = table.select("author_raw").distinct().execute()["author_raw"].tolist()
    # Only authors who sent actual messages appear (not system message participants)
    # Franklin sent multiple messages, Eurico Max sent one message
    # "Iuri Brasil" and "Você" only appear in system messages, not as message authors
    for expected in ("Franklin", "Eurico Max"):
        assert expected in authors, f"Expected '{expected}' in authors, got {authors}"
    # Verify system-only participants are NOT included
    assert "Iuri Brasil" not in authors, "Iuri Brasil never sent messages, should not be in authors"
    assert "Você" not in authors, "'Você' only appears in system messages, should not be in authors"


def test_anonymization_is_deterministic(whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback):
    """Test that anonymization produces same UUIDs for same names."""
    export = create_export_from_fixture(whatsapp_fixture)
    table_one = parse_source(export, timezone=whatsapp_fixture.timezone)
    table_two = parse_source(export, timezone=whatsapp_fixture.timezone)

    authors_one = sorted(table_one.select("author_uuid").distinct().execute()["author_uuid"].tolist())
    authors_two = sorted(table_two.select("author_uuid").distinct().execute()["author_uuid"].tolist())

    assert authors_one == authors_two


def test_anonymized_uuids_are_valid_format(whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback):
    """Test that anonymized UUIDs follow expected format (full UUID format)."""
    import uuid

    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    distinct_authors = table.select("author_uuid").distinct().execute()["author_uuid"].tolist()
    authors = [value for value in distinct_authors if value not in {"system", "egregora"}]

    # Validate each author ID is a valid UUID (36 characters with hyphens)
    for author_id in authors:
        assert len(author_id) == 36, f"Expected UUID length 36, got {len(author_id)} for '{author_id}'"
        try:
            uuid.UUID(author_id)
        except ValueError as e:
            pytest.fail(f"Invalid UUID format for '{author_id}': {e}")


# =============================================================================
# Media Extraction Tests
# =============================================================================


# =============================================================================
# Message Filtering Tests
# =============================================================================


def test_egregora_commands_are_filtered_out(whatsapp_fixture: WhatsAppFixture, mock_dynamic_regex_fallback):
    """Test that egregora in-chat commands are filtered from the message stream."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    original_records = table.execute().to_dict("records")
    sample_record = original_records[0]
    # ibis.memtable requires JSON columns to be strings rather than dict instances
    for json_key in ("attrs", "pii_flags"):
        value = sample_record.get(json_key)
        if isinstance(value, dict):
            sample_record[json_key] = json.dumps(value)
    synthetic = {
        **sample_record,
        "text": "/egregora opt-out",
    }
    augmented = table.union(ibis.memtable([synthetic], schema=table.schema()))

    filtered, removed_count = filter_egregora_messages(augmented)
    assert removed_count == 1

    messages = " ".join(filtered["text"].execute().dropna().tolist())
    assert "/egregora opt-out" not in messages


# =============================================================================
# Enrichment Tests
# =============================================================================
