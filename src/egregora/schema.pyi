from __future__ import annotations

from zoneinfo import ZoneInfo
from typing import Any

from ibis.expr.types import Table

MESSAGE_SCHEMA: dict[str, Any]

def ensure_message_schema(
    df: Table,
    *,
    timezone: str | ZoneInfo | None = ...,
) -> Table: ...
