"""Path-related utilities (V2 compatibility shim).

This module now re-exports the canonical ``slugify`` implementation from V3
to maintain backward compatibility for existing V2 imports.

New code should prefer importing from ``egregora_v3.core.utils``.
"""

from egregora_v3.core.utils import slugify

__all__ = ["slugify"]
