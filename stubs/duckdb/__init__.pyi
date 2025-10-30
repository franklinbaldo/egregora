from __future__ import annotations

from typing import Any

class DuckDBPyConnection:
    def execute(self, *args: Any, **kwargs: Any) -> Any: ...

class DuckDBPyRelation:
    ...

def connect(*args: Any, **kwargs: Any) -> DuckDBPyConnection: ...

def from_connection(*args: Any, **kwargs: Any) -> DuckDBPyRelation: ...

__all__ = ["connect", "from_connection", "DuckDBPyConnection", "DuckDBPyRelation"]
