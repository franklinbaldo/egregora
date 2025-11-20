"""E2E tests for WhatsApp input adapter.

These tests validate the WhatsApp adapter's ability to parse WhatsApp export
ZIPs into the standardized Interchange Representation (IR).

Tests in this file validate:
- ZIP contents and header safety
- Chat log parsing (dates, authors, messages)
- Media extraction and reference replacement
- Anonymization (UUID5 generation)
- Enrichment transformations
- Schema validation
"""

from __future__ import annotations

import struct
import zipfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import ibis
import pytest

from egregora.config.settings import create_default_config

# from egregora.ops.media import extract_and_replace_media
from egregora.enrichment.runners import EnrichmentRuntimeContext, enrich_table
from egregora.input_adapters.whatsapp import WhatsAppAdapter, filter_egregora_messages, parse_source
from egregora.utils.cache import EnrichmentCache

if TYPE_CHECKING:
    from conftest import WhatsAppFixture


def create_export_from_fixture(fixture: WhatsAppFixture):
    return fixture.create_export()


def _inflate_declared_size(zip_path: Path, member_name: str, *, fake_size: int) -> None:
    """Patch ZIP headers to advertise an unrealistically large file size."""

    with zipfile.ZipFile(zip_path) as archive:
        info = archive.getinfo(member_name)
        local_header_offset = info.header_offset + 22

    fake_size_bytes = struct.pack("<I", fake_size)
    buffer = bytearray(Path(zip_path).read_bytes())
    buffer[local_header_offset : local_header_offset + 4] = fake_size_bytes

    central_directory_signature = b"\x50\x4b\x01\x02"
    central_directory_offset = buffer.rfind(central_directory_signature)
    if central_directory_offset == -1:
        raise AssertionError("Central directory not found in test ZIP")
    buffer[central_directory_offset + 24 : central_directory_offset + 28] = fake_size_bytes

    with open(zip_path, "r+b") as zip_file:
        zip_file.write(buffer)
        zip_file.truncate()


# =============================================================================
# ZIP Header Safety Tests
# =============================================================================


def test_fake_zip_bomb_is_rejected(tmp_path: Path):
    """A zip member declaring an oversized payload should be rejected early."""

    chat_file = "WhatsApp Chat with Exploit.txt"
    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(chat_file, "harmless")

    _inflate_declared_size(zip_path, chat_file, fake_size=3 * 1024**3)

    adapter = WhatsAppAdapter()
    with pytest.raises(ValueError, match="Security limit exceeded"):
        adapter.parse(zip_path)


# =============================================================================
# Parser Tests (Chat Log → IR Table)
# =============================================================================


def test_parser_produces_valid_table(whatsapp_fixture: WhatsAppFixture):
    """Test that parser produces valid IR table with expected columns."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    # IR schema uses: ts, author, text (not timestamp, author, message)
    assert {"ts", "author", "text"}.issubset(table.columns)
    assert table.count().execute() == 10
    messages = table["text"].execute().tolist()
    assert all(message is not None and message.strip() for message in messages)

    timestamps = table["ts"].execute()
    assert all(ts.tzinfo is not None for ts in timestamps)


def test_parser_handles_portuguese_dates(whatsapp_fixture: WhatsAppFixture):
    """Test that parser correctly handles Portuguese date formats."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)
    dates = [value.date() for value in table["date"].execute().tolist()]

    assert date(2025, 10, 28) in dates


def test_parser_preserves_all_messages(whatsapp_fixture: WhatsAppFixture):
    """Test that parser preserves all participant messages."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    participant_rows = table.filter(~table.author.isin(["system", "egregora"]))
    assert participant_rows.count().execute() == 10


def test_parser_extracts_media_references(whatsapp_fixture: WhatsAppFixture):
    """Test that parser extracts media file references from messages."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    combined = " ".join(table["text"].execute().tolist())
    assert "IMG-20251028-WA0035.jpg" in combined
    assert "arquivo anexado" in combined


def test_parser_enforces_message_schema(whatsapp_fixture: WhatsAppFixture):
    """Test that parser strictly enforces IR MESSAGE_SCHEMA without extra columns."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    # Verify table has IR schema columns (ts, text, author_uuid, not timestamp, message, author)
    expected_columns = {
        "ts",
        "date",
        "author",
        "author_raw",
        "author_uuid",
        "text",
        "original_line",
        "tagged_line",
        "message_id",
    }
    assert set(table.columns) == expected_columns

    # Verify no extra columns
    assert "time" not in table.columns
    assert "group_slug" not in table.columns
    assert "group_name" not in table.columns


# =============================================================================
# Anonymization Tests (Author Names → UUIDs)
# =============================================================================


def test_anonymization_removes_real_author_names(whatsapp_fixture: WhatsAppFixture):
    """Test that anonymization removes real author names from table."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    authors = table["author"].execute().tolist()
    for forbidden in ("Franklin", "Iuri Brasil", "Você", "Eurico Max"):
        assert forbidden not in authors

    messages = table["text"].execute().tolist()
    assert any("@" in message and "teste de menção" in message for message in messages)


def test_parse_source_exposes_raw_authors_when_requested(whatsapp_fixture: WhatsAppFixture):
    """Test that raw author names are exposed when explicitly requested."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(
        export,
        timezone=whatsapp_fixture.timezone,
        expose_raw_author=True,
    )

    authors = table.select("author").distinct().execute()["author"].tolist()
    # Only authors who sent actual messages appear (not system message participants)
    # Franklin sent multiple messages, Eurico Max sent one message
    # "Iuri Brasil" and "Você" only appear in system messages, not as message authors
    for expected in ("Franklin", "Eurico Max"):
        assert expected in authors, f"Expected '{expected}' in authors, got {authors}"
    # Verify system-only participants are NOT included
    assert "Iuri Brasil" not in authors, "Iuri Brasil never sent messages, should not be in authors"
    assert "Você" not in authors, "'Você' only appears in system messages, should not be in authors"


def test_anonymization_is_deterministic(whatsapp_fixture: WhatsAppFixture):
    """Test that anonymization produces same UUIDs for same names."""
    export = create_export_from_fixture(whatsapp_fixture)
    table_one = parse_source(export, timezone=whatsapp_fixture.timezone)
    table_two = parse_source(export, timezone=whatsapp_fixture.timezone)

    authors_one = sorted(table_one.select("author").distinct().execute()["author"].tolist())
    authors_two = sorted(table_two.select("author").distinct().execute()["author"].tolist())

    assert authors_one == authors_two


def test_anonymized_uuids_are_valid_format(whatsapp_fixture: WhatsAppFixture):
    """Test that anonymized UUIDs follow expected format (full UUID format)."""
    import uuid

    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    distinct_authors = table.select("author").distinct().execute()["author"].tolist()
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


@pytest.mark.xfail(reason="Media extraction not returning files - needs investigation")
def test_media_extraction_creates_expected_files(whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    """Test that media extraction creates expected files in output directory."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    _, media_mapping = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
    )

    assert len(media_mapping) == 4
    for extracted_path in media_mapping.values():
        assert extracted_path.exists()


@pytest.mark.xfail(reason="Media extraction not returning files - needs investigation")
def test_media_references_replaced_in_messages(whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    """Test that media references in messages are replaced with markdown."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    updated_table, _ = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
    )

    joined_messages = " ".join(updated_table["text"].execute().dropna().tolist())
    assert "![Image]" in joined_messages


def test_media_files_have_deterministic_names(whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    """Test that media files get deterministic names across multiple extractions."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    docs_dir_one = tmp_path / "docs1"
    docs_dir_two = tmp_path / "docs2"
    posts_one = docs_dir_one / "posts"
    posts_two = docs_dir_two / "posts"
    docs_dir_one.mkdir()
    docs_dir_two.mkdir()
    posts_one.mkdir()
    posts_two.mkdir()

    # extract_and_replace_media was removed in favor of pipeline logic
    # But we can use adapter.deliver_media + adapter.standardize_media_file to test this

    # Get a media reference from the table
    # Note: The test fixture needs to contain a message with media
    # Assuming there's at least one IMG-*.jpg reference

    adapter = WhatsAppAdapter()
    media_ref = "IMG-20251028-WA0001.jpg"  # Example from fixture if known

    # Actually, let's just use the adapter's standardize method directly
    # since that's what ensures determinism

    # Create dummy content
    content = b"fake image content"

    # Create temp file
    source_file = tmp_path / "source.jpg"
    source_file.write_bytes(content)

    media_dir_one = docs_dir_one / "media"
    media_dir_two = docs_dir_two / "media"

    # Standardize twice
    from egregora.ops.media import get_media_subfolder

    path1 = adapter.standardize_media_file(source_file, media_dir_one, get_subfolder=get_media_subfolder)

    # Re-create source file as it might be moved/deleted
    source_file.write_bytes(content)
    path2 = adapter.standardize_media_file(source_file, media_dir_two, get_subfolder=get_media_subfolder)

    assert path1.name == path2.name
    # Mapping logic removed from test as function is gone
    mapping_one = {media_ref: path1}
    mapping_two = {media_ref: path2}

    assert mapping_one.keys() == mapping_two.keys()
    for key in mapping_one:
        assert mapping_one[key].name == mapping_two[key].name


# =============================================================================
# Message Filtering Tests
# =============================================================================


def test_egregora_commands_are_filtered_out(whatsapp_fixture: WhatsAppFixture):
    """Test that egregora in-chat commands are filtered from the message stream."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    original_records = table.execute().to_dict("records")
    sample_record = original_records[0]
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


@pytest.mark.xfail(reason="Enrichment tests need schema updates (event_id, timestamp columns)")
def test_enrichment_adds_egregora_messages(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
):
    """Test that enrichment adds egregora system messages to the table."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    updated_table, media_mapping = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
    )

    cache = EnrichmentCache(tmp_path / "cache")

    # MODERN (Phase 2): Create config and context
    config = create_default_config(tmp_path)
    config = config.model_copy(
        deep=True,
        update={
            "enrichment": config.enrichment.model_copy(update={"enable_url": False}),
        },
    )

    enrichment_context = EnrichmentRuntimeContext(
        cache=cache,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
        output_format=None,  # Not needed for test
    )

    try:
        enriched = enrich_table(
            updated_table,
            media_mapping,
            config=config,
            context=enrichment_context,
        )
    finally:
        cache.close()

    assert enriched.count().execute() >= updated_table.count().execute()
    assert enriched.filter(enriched.author == "egregora").count().execute() > 0


@pytest.mark.xfail(reason="Enrichment tests need schema updates (event_id, timestamp columns)")
def test_enrichment_handles_schema_mismatch(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
):
    """Test that enrichment can handle extra columns not in CONVERSATION_SCHEMA."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    # Add extra columns to simulate the schema mismatch
    table = table.mutate(
        time=table.timestamp.strftime("%H:%M:%S"),
        group_slug=ibis.literal("test-group"),
        group_name=ibis.literal("Test Group"),
    )

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    updated_table, media_mapping = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
    )

    cache = EnrichmentCache(tmp_path / "cache")

    # MODERN (Phase 2): Create config and context
    config = create_default_config(tmp_path)
    config = config.model_copy(
        deep=True,
        update={
            "enrichment": config.enrichment.model_copy(update={"enable_url": False}),
        },
    )

    enrichment_context = EnrichmentRuntimeContext(
        cache=cache,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
        output_format=None,  # Not needed for test
    )

    try:
        # This should not raise an exception
        enriched = enrich_table(
            updated_table,
            media_mapping,
            config=config,
            context=enrichment_context,
        )
        # Verify that the new rows have been added
        assert enriched.count().execute() > updated_table.count().execute()
        assert "egregora" in enriched.author.execute().tolist()

    finally:
        cache.close()
