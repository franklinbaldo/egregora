"""Backward-compatible shim for annotation functionality.

DEPRECATED: This module re-exports from egregora.agents.shared.annotations.
Please update imports to use the new location:

    from egregora.agents.shared.annotations import AnnotationStore, Annotation, ...

This shim will be removed in a future version.
"""

from __future__ import annotations

import warnings

# Re-export all public API from new location
from egregora.agents.shared.annotations import (
    ANNOTATION_AUTHOR,
    ANNOTATIONS_TABLE,
    Annotation,
    AnnotationStore,
)

__all__ = [
    "ANNOTATIONS_TABLE",
    "ANNOTATION_AUTHOR",
    "Annotation",
    "AnnotationStore",
]


def __getattr__(name: str) -> object:
    """Emit deprecation warning for public API attribute access."""
    # Don't warn for module internals
    if name.startswith("__"):
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    # Only warn for public API attributes
    if name in __all__:
        warnings.warn(
            f"Importing '{name}' from egregora.knowledge.annotations is deprecated. "
            f"Use 'from egregora.agents.shared.annotations import {name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return globals()[name]

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
