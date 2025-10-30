from __future__ import annotations

from zipfile import ZipFile

class ZipValidationError(ValueError):
    ...

def validate_zip_contents(zf: ZipFile) -> None: ...

def ensure_safe_member_size(zf: ZipFile, member_name: str) -> None: ...
