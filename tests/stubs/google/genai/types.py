from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Part:
    text: str | None = None
    file_uri: str | None = None

    @classmethod
    def from_text(cls, text: str) -> "Part":
        return cls(text=text)

    @classmethod
    def from_uri(cls, file_uri: str) -> "Part":
        return cls(file_uri=file_uri)


@dataclass
class Content:
    role: str
    parts: List[Part]


@dataclass
class GenerateContentConfig:
    temperature: float
    response_mime_type: str


__all__ = ["Part", "Content", "GenerateContentConfig"]
