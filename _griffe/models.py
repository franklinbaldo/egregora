"""Minimal stub models that emulate the behaviour required in tests."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import List

from .enumerations import DocstringSectionKind


@dataclass
class Object:
    """Placeholder object type used purely for typing compatibility."""


@dataclass
class Docstring:
    """Simplistic docstring parser used as a lightweight substitute."""

    value: str
    lineno: int = 1
    parser: str | None = None
    parent: Object | None = None

    def parse(self) -> List[SimpleNamespace]:
        """Return a best-effort interpretation of the docstring."""

        stripped = self.value.strip()
        sections: list[SimpleNamespace] = []

        if stripped:
            sections.append(SimpleNamespace(kind=DocstringSectionKind.text, value=stripped))

        return sections


__all__ = ["Docstring", "Object"]
