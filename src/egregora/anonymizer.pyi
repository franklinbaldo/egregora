from __future__ import annotations

from typing import Any

from ibis.expr.types import Table

NAMESPACE_AUTHOR: Any
SYSTEM_AUTHOR: str

MENTION_PATTERN: Any

def anonymize_author(author: str) -> str: ...

def anonymize_mentions(text: str) -> str: ...

def anonymize_dataframe(df: Table) -> Table: ...
