import ibis
import pytest

from egregora.database.views import (
    COMMON_VIEWS,
    chunks_view,
    daily_aggregates_view,
    get_view_builder,
    hourly_aggregates_view,
    list_common_views,
    messages_with_media_view,
    messages_with_text_view,
)


def test_common_views_registry_contents() -> None:
    """All expected view builders are exposed in COMMON_VIEWS."""

    expected = {
        "chunks",
        "chunks_optimized",
        "messages_with_media",
        "messages_with_text",
        "hourly_aggregates",
        "daily_aggregates",
    }

    assert set(COMMON_VIEWS) == expected
    assert list_common_views() == sorted(expected)


def test_get_view_builder_unknown() -> None:
    """Requesting an unknown view name raises KeyError."""

    with pytest.raises(KeyError, match="Unknown view"):
        get_view_builder("does-not-exist")


def test_chunks_view_adds_chunk_idx() -> None:
    import uuid
    from datetime import datetime

    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    id3 = str(uuid.uuid4())
    t1 = str(uuid.uuid4())
    t2 = str(uuid.uuid4())

    data = {
        "event_id": [id1, id2, id3],
        "thread_id": [t1, t1, t2],
        "ts": [
            datetime(2025, 1, 1, 10, 0),
            datetime(2025, 1, 1, 11, 0),
            datetime(2025, 1, 1, 10, 30),
        ],
        "text": ["msg1", "msg2", "msg3"],
    }
    schema = {
        "event_id": "uuid",
        "thread_id": "uuid",
        "ts": "timestamp",
        "text": "string",
    }
    table = ibis.memtable(data, schema=schema)

    result = chunks_view(table)
    df = result.execute()

    assert "chunk_idx" in df.columns


def test_messages_with_media_view_filters_rows() -> None:
    data = {
        "event_id": ["id1", "id2", "id3"],
        "text": ["msg1", "msg2", "msg3"],
        "media_url": ["http://example.com/img.jpg", None, "http://example.com/vid.mp4"],
    }
    schema = {"event_id": "string", "text": "string", "media_url": "string"}
    table = ibis.memtable(data, schema=schema)

    result = messages_with_media_view(table)
    df = result.execute()

    assert len(df) == 2
    assert all(df["media_url"].notnull())


def test_messages_with_text_view_filters_rows() -> None:
    data = {
        "event_id": ["id1", "id2", "id3", "id4"],
        "text": ["hello", None, "", "world"],
    }
    schema = {"event_id": "string", "text": "string"}
    table = ibis.memtable(data, schema=schema)

    result = messages_with_text_view(table)
    df = result.execute()

    assert len(df) == 2
    assert list(df["text"]) == ["hello", "world"]


def test_hourly_aggregates_view() -> None:
    import uuid
    from datetime import datetime

    data = {
        "ts": [
            datetime(2025, 1, 1, 10, 15),
            datetime(2025, 1, 1, 10, 30),
            datetime(2025, 1, 1, 11, 15),
            datetime(2025, 1, 1, 11, 30),
        ],
        "author_uuid": [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ],
    }
    schema = {"ts": "timestamp", "author_uuid": "uuid"}
    table = ibis.memtable(data, schema=schema)

    result = hourly_aggregates_view(table)
    df = result.execute()

    assert len(df) == 2
    assert {"hour", "message_count", "unique_authors"}.issubset(df.columns)


def test_daily_aggregates_view() -> None:
    import uuid
    from datetime import datetime

    data = {
        "ts": [
            datetime(2025, 1, 1, 10, 0),
            datetime(2025, 1, 1, 14, 0),
            datetime(2025, 1, 2, 10, 0),
        ],
        "author_uuid": [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ],
    }
    schema = {"ts": "timestamp", "author_uuid": "uuid"}
    table = ibis.memtable(data, schema=schema)

    result = daily_aggregates_view(table)
    df = result.execute()

    assert len(df) == 2
    assert {"day", "message_count"}.issubset(df.columns)
