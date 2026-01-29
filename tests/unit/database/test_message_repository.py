"""Tests for the MessageRepository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import ibis
import pytest
from ibis.backends.duckdb import Backend as DuckDBBackend

from egregora.database.message_repository import MessageRepository
from egregora.database.schemas import STAGING_MESSAGES_SCHEMA

# A consistent timestamp for reproducible tests
NOW = datetime.now(UTC)


@pytest.fixture
def db_connection() -> DuckDBBackend:
    """Fixture to provide an in-memory DuckDB Ibis connection."""
    return ibis.duckdb.connect()


@pytest.fixture
def messages_table(db_connection: DuckDBBackend) -> ibis.expr.types.Table:
    """Fixture to create and populate the messages table for testing."""
    db_connection.create_table("messages", schema=STAGING_MESSAGES_SCHEMA, overwrite=True)
    table = db_connection.table("messages")

    test_data = [
        # No URL
        {"event_id": "1", "ts": NOW, "text": "Hello world", "author_raw": "Alice"},
        # Single URL, should be picked up
        {
            "event_id": "2",
            "ts": NOW + timedelta(minutes=1),
            "text": "Check out https://example.com/one",
            "author_raw": "Bob",
        },
        # Duplicate URL, earlier timestamp. This is the one that should be kept.
        {
            "event_id": "3",
            "ts": NOW - timedelta(minutes=5),
            "text": "Earlier message about https://example.com/two",
            "author_raw": "Charlie",
        },
        # No URL
        {"event_id": "4", "ts": NOW + timedelta(minutes=2), "text": "Just chatting", "author_raw": "Alice"},
        # Duplicate URL, later timestamp. Metadata should be ignored.
        {
            "event_id": "5",
            "ts": NOW + timedelta(minutes=3),
            "text": "Someone else mentioned https://example.com/two",
            "author_raw": "David",
        },
        # A third unique URL
        {
            "event_id": "6",
            "ts": NOW + timedelta(minutes=4),
            "text": "And https://example.com/three is here",
            "author_raw": "Eve",
        },
        # A message with two URLs, both new
        {
            "event_id": "7",
            "ts": NOW + timedelta(minutes=5),
            "text": "Here are two links: https://example.com/four and http://example.com/five",
            "author_raw": "Frank",
        },
    ]

    # Ibis 9.x requires converting data to a DataFrame first
    import pandas as pd  # noqa: TID251

    df = pd.DataFrame(test_data)

    # Fill missing columns with None to match the full schema
    for col in STAGING_MESSAGES_SCHEMA.names:
        if col not in df.columns:
            df[col] = None

    db_connection.insert("messages", df)
    return table


def test_get_url_enrichment_candidates(db_connection, messages_table):
    """Verify that the repository correctly extracts URL enrichment candidates."""
    repo = MessageRepository(db_connection)

    # Ask for 3 candidates
    candidates = repo.get_url_enrichment_candidates(messages_table, max_enrichments=3)

    # 1. VERIFY COUNT
    assert len(candidates) == 3, "Should return exactly 3 candidates as per the limit"

    # 2. VERIFY CONTENT & ORDER
    urls = [url for url, metadata in candidates]
    assert urls == [
        "https://example.com/two",
        "https://example.com/one",
        "https://example.com/three",
    ], "URLs should be unique and sorted by the earliest timestamp"

    # 3. VERIFY METADATA
    # Check the metadata for the deduplicated URL. It should come from event_id "3".
    url_two_metadata = next(metadata for url, metadata in candidates if url == "https://example.com/two")
    assert url_two_metadata["event_id"] == "3", "Metadata should be from the earliest message"


def test_get_url_enrichment_candidates_with_no_limit(db_connection, messages_table):
    """Verify that all unique URLs are returned when no limit is set."""
    repo = MessageRepository(db_connection)

    # Ask for all candidates
    candidates = repo.get_url_enrichment_candidates(messages_table, max_enrichments=999)

    assert len(candidates) == 5
    urls = [url for url, metadata in candidates]
    assert urls == [
        "https://example.com/two",
        "https://example.com/one",
        "https://example.com/three",
        "http://example.com/five",
        "https://example.com/four",
    ]


def test_get_url_enrichment_candidates_empty_table(db_connection):
    """Verify that it returns an empty list for an empty table."""
    db_connection.create_table("empty_messages", schema=STAGING_MESSAGES_SCHEMA, overwrite=True)
    table = db_connection.table("empty_messages")
    repo = MessageRepository(db_connection)

    candidates = repo.get_url_enrichment_candidates(table, max_enrichments=10)
    assert candidates == []


def test_get_media_enrichment_candidates(db_connection):
    """Verify that the repository correctly extracts media enrichment candidates."""
    db_connection.create_table("media_messages", schema=STAGING_MESSAGES_SCHEMA, overwrite=True)

    test_data = [
        {"event_id": "1", "ts": NOW, "text": "Here is an image: media.jpg", "author_raw": "Alice"},
        {
            "event_id": "2",
            "ts": NOW + timedelta(minutes=1),
            "text": "Another one: video.mp4",
            "author_raw": "Bob",
        },
        {
            "event_id": "3",
            "ts": NOW - timedelta(minutes=5),
            "text": "Earlier message about media.jpg",
            "author_raw": "Charlie",
        },
    ]

    import pandas as pd  # noqa: TID251

    df = pd.DataFrame(test_data)

    for col in STAGING_MESSAGES_SCHEMA.names:
        if col not in df.columns:
            df[col] = None

    db_connection.insert("media_messages", df)
    table = db_connection.table("media_messages")

    repo = MessageRepository(db_connection)

    candidates = repo.get_media_enrichment_candidates(table, media_mapping={}, limit=2)

    assert len(candidates) == 2

    refs = [ref for ref, doc, metadata in candidates]
    assert "media.jpg" in refs
    assert "video.mp4" in refs

    jpg_metadata = next(metadata for ref, doc, metadata in candidates if ref == "media.jpg")
    assert jpg_metadata["event_id"] == "3"


def test_get_media_enrichment_candidates_with_uuid(db_connection):
    """Verify that the repository correctly extracts media candidates referenced by UUID."""
    db_connection.create_table("uuid_media_messages", schema=STAGING_MESSAGES_SCHEMA, overwrite=True)

    media_uuid = "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6.jpg"
    test_data = [
        {
            "event_id": "1",
            "ts": NOW,
            "text": f"Check out this media: {media_uuid}",
            "author_raw": "Alice",
            "media_type": "image",
        },
    ]

    import pandas as pd  # noqa: TID251

    df = pd.DataFrame(test_data)

    for col in STAGING_MESSAGES_SCHEMA.names:
        if col not in df.columns:
            df[col] = None

    db_connection.insert("uuid_media_messages", df)
    table = db_connection.table("uuid_media_messages")

    repo = MessageRepository(db_connection)

    candidates = repo.get_media_enrichment_candidates(table, media_mapping={}, limit=1)

    assert len(candidates) == 1
    ref, _, _ = candidates[0]
    assert ref == media_uuid
