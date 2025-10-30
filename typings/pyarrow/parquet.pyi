from __future__ import annotations

from os import PathLike

class FileMetaData:
    num_rows: int


def read_metadata(source: str | PathLike[str]) -> FileMetaData: ...

__all__ = [
    "FileMetaData",
    "read_metadata",
]
