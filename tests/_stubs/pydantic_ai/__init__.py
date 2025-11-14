"""Minimal stub of pydantic_ai for tests."""

from __future__ import annotations

from dataclasses import dataclass


class Agent:  # pragma: no cover - stub behaviour not exercised
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs


class ModelMessagesTypeAdapter:  # pragma: no cover - stub behaviour not exercised
    pass


@dataclass
class RunContext:  # pragma: no cover - stub behaviour not exercised
    state: dict | None = None
