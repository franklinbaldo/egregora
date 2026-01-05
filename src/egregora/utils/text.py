"""Text-related utilities (V2 compatibility shim).

This module is now a compatibility shim that re-exports text utilities
from the V3 core. New code should import directly from `egregora_v3.core.utils`.
"""

from egregora_v3.core.utils import (
    InvalidInputError,
    SlugifyError,
    slugify,
    slugify_case,
    slugify_lower,
)

__all__ = [
    "InvalidInputError",
    "SlugifyError",
    "slugify",
    "slugify_case",
    "slugify_lower",
]
