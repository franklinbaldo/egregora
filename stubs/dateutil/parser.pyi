from __future__ import annotations

from datetime import datetime
from typing import Any

def parse(timestr: str, *args: Any, **kwargs: Any) -> datetime: ...

def isoparse(timestr: str) -> datetime: ...
