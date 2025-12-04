"""Windowing Logic for the V3 Pipeline.

Implements strategies to slice a continuous stream of Entries into batches (windows)
suitable for LLM processing.
"""

from __future__ import annotations

from typing import Protocol, Iterator, List
from datetime import timedelta
from egregora_v3.core.types import Entry

class WindowingStrategy(Protocol):
    """Protocol for windowing strategies."""

    def window(self, entries: Iterator[Entry]) -> Iterator[List[Entry]]:
        """Yield batches of entries."""
        ...


class TimeWindowStrategy:
    """Windows entries by time duration (e.g., 24 hours)."""

    def __init__(self, duration: timedelta):
        self.duration = duration

    def window(self, entries: Iterator[Entry]) -> Iterator[List[Entry]]:
        """Slice entries into time-based windows.

        Assumes input entries are sorted by 'updated' or timestamp.
        """
        current_window: List[Entry] = []
        window_start = None

        for entry in entries:
            # Skip entries without timestamp (shouldn't happen in valid Atom)
            if not entry.updated:
                continue

            if window_start is None:
                window_start = entry.updated
                current_window.append(entry)
                continue

            # Check if entry falls outside current window duration
            if entry.updated - window_start > self.duration:
                yield current_window
                # Start new window
                current_window = [entry]
                window_start = entry.updated
            else:
                current_window.append(entry)

        # Yield remaining
        if current_window:
            yield current_window


class CountWindowStrategy:
    """Windows entries by count (e.g., 50 messages)."""

    def __init__(self, size: int):
        self.size = size

    def window(self, entries: Iterator[Entry]) -> Iterator[List[Entry]]:
        current_window: List[Entry] = []
        for entry in entries:
            current_window.append(entry)
            if len(current_window) >= self.size:
                yield current_window
                current_window = []

        if current_window:
            yield current_window
