"""Path-related utilities, including slugification."""

# THIS IS A COMPATIBILITY SHIM
# The canonical implementation is now in `egregora_v3.core.utils`
# This file should be removed once all V2 code is migrated.
from egregora_v3.core.utils import slugify

__all__ = ["slugify"]
