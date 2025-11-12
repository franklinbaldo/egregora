"""Shared type aliases used across the project."""

from __future__ import annotations

from typing import NewType

GroupSlug = NewType("GroupSlug", str)
PostSlug = NewType("PostSlug", str)
__all__ = ["GroupSlug"]
