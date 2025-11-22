from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from pydantic_ai.usage import RunUsage


@dataclass
class UsageTracker:
    """Track aggregated LLM usage metrics."""

    usage: RunUsage = RunUsage()
    history: deque[RunUsage] = deque()

    def record(self, run_usage: RunUsage) -> None:
        """Add usage and keep history for debugging."""
        self.usage.incr(run_usage)
        self.history.append(run_usage)
        if len(self.history) > 50:
            self.history.popleft()

    def snapshot(self) -> RunUsage:
        """Return cumulative usage."""
        return self.usage
