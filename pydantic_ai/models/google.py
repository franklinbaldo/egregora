"""Tiny stub of `pydantic_ai.models.google` for unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class GoogleModelSettings:
    """Structure matching the attributes the code under test relies on."""

    google_tools: Any | None = None


__all__ = ["GoogleModelSettings"]

