"""Path-related utilities, including slugification."""
# V2 Compatibility Shim
# The canonical `slugify` now lives in the V3 core. This module re-exports
# it to ensure that any V2 code relying on the old import path does not break.
# New code should import directly from the V3 module.
from egregora.utils.exceptions import InvalidInputError as V2InvalidInputError
from egregora_v3.core.utils import InvalidInputError as V3InvalidInputError
from egregora_v3.core.utils import slugify as v3_slugify


def slugify(text: str, max_len: int = 60, *, lowercase: bool = True) -> str:
    """V2 compatibility wrapper for the V3 slugify function."""
    try:
        return v3_slugify(text, max_len=max_len, lowercase=lowercase)
    except V3InvalidInputError as e:
        raise V2InvalidInputError(str(e)) from e


__all__ = ["slugify"]
