"""Minimal enumerations required by :mod:`pydantic_ai` during tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _DocstringSectionKind:
    """Simple value object mirroring the API from the real extension."""

    name: str


class DocstringSectionKind:
    """Subset of section kinds exercised in the test-suite."""

    parameters = _DocstringSectionKind("parameters")
    text = _DocstringSectionKind("text")


__all__ = ["DocstringSectionKind"]
