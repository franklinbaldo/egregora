from typing import Any

Table = Any

def __getattr__(name: str) -> Any: ...
