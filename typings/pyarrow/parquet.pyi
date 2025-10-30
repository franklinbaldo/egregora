from __future__ import annotations

from os import PathLike
from typing import Any

from . import Table

class FileMetaData:
    num_rows: int


def read_metadata(path: str | PathLike[str] | bytes | PathLike[bytes]) -> FileMetaData: ...

def read_table(*args: Any, **kwargs: Any) -> Table: ...

def write_table(*args: Any, **kwargs: Any) -> None: ...

__all__ = [
    "FileMetaData",
    "read_metadata",
    "read_table",
    "write_table",
]
