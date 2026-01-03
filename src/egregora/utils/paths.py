"""Shim for backward compatibility.

The `slugify` utility has been moved to `egregora_v3.core.utils`.
This shim re-exports it from its original location to avoid breaking
existing imports. New code should import directly from the v3 module.
"""

from egregora_v3.core.utils import slugify

__all__ = ["slugify"]
