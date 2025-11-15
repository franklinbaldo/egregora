"""Minimal subset of the `pydantic_ai.messages` namespace used in tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BinaryContent:
    """Simple container for binary payloads with a MIME type."""

    data: bytes
    media_type: str | None = None


__all__ = ["BinaryContent"]

