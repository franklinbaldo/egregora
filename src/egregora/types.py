"""Shared type aliases used across the project."""

from __future__ import annotations

from typing import NewType

# ``GroupSlug`` identifies a WhatsApp group (real or virtual) that the
# pipeline knows how to process. Keeping it distinct from ``PostSlug`` helps
# prevent accidental mixing of identifiers that live in different namespaces.
GroupSlug = NewType("GroupSlug", str)

# ``PostSlug`` identifies a generated blog post (usually derived from the
# output path or file stem). Both slug types currently alias ``str`` at
# runtime, but type checkers can now flag incorrect usage when they are mixed.
PostSlug = NewType("PostSlug", str)

__all__ = ["GroupSlug", "PostSlug"]
