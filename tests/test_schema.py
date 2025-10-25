from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import ibis
import ibis.expr.datatypes as dt

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "egregora.schema", Path(__file__).resolve().parents[1] / "src" / "egregora" / "schema.py"
)
_schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_schema)
ensure_message_schema = _schema.ensure_message_schema

def test_ensure_message_schema_with_datetime_objects():
    table = ibis.memtable(
        [
            {"timestamp": datetime(2025, 1, 1, 12, 0, 0), "author": "test", "message": "hello"}
        ]
    )

    result = ensure_message_schema(table)

    assert result.schema()["timestamp"] == dt.Timestamp(timezone="UTC", scale=9)
    executed = result.execute()
    assert str(executed["timestamp"].dt.tz) == "UTC"


def test_ensure_message_schema_with_tz_aware_datetime():
    aware = datetime(2025, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    table = ibis.memtable(
        [{"timestamp": aware, "author": "test", "message": "hello"}]
    )

    result = ensure_message_schema(table)

    assert result.schema()["timestamp"] == dt.Timestamp(timezone="UTC", scale=9)
    executed = result.execute()
    assert str(executed["timestamp"].dt.tz) == "UTC"
    assert executed["timestamp"][0] == aware.astimezone(timezone.utc)


def test_ibis_normalises_naive_timestamp_with_timezone():
    table = ibis.memtable(
        [
            {
                "timestamp": datetime(2024, 5, 1, 8, 30),
                "author": "alice",
                "message": "hi",
                "original_line": "hi",
                "tagged_line": "hi",
            }
        ]
    )

    normalised = ensure_message_schema(table, timezone="America/Sao_Paulo")
    df = normalised.execute()

    assert str(df["timestamp"].dt.tz) == "America/Sao_Paulo"
    assert df["timestamp"].dt.hour.iloc[0] == 8


def test_ibis_converts_existing_timezone_to_requested():
    table = ibis.memtable(
        [
            {
                "timestamp": datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc),
                "author": "bob",
                "message": "hello",
                "original_line": "hello",
                "tagged_line": "hello",
            }
        ]
    )

    normalised = ensure_message_schema(table, timezone="America/Sao_Paulo")
    df = normalised.execute()

    assert str(df["timestamp"].dt.tz) == "America/Sao_Paulo"
    # UTC noon should map to 09:00 in Sao Paulo (-03:00) during May
    assert df["timestamp"].dt.hour.iloc[0] == 9
