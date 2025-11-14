"""Minimal message stubs for pydantic_ai."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TextPart:  # pragma: no cover - stub for type checking
    text: str


@dataclass
class ThinkingPart:  # pragma: no cover
    text: str


@dataclass
class ToolCallPart:  # pragma: no cover
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolReturnPart:  # pragma: no cover
    name: str
    content: Any


@dataclass
class ModelRequest:  # pragma: no cover
    content: list[Any]


@dataclass
class ModelResponse:  # pragma: no cover
    content: list[Any]


@dataclass
class BinaryContent:  # pragma: no cover
    mime_type: str
    data: bytes
