from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from pydantic_ai.usage import RunUsage


@dataclass
class UsageTracker:
    """Track aggregated LLM usage metrics."""

    usage: RunUsage = field(default_factory=RunUsage)
    history: deque[RunUsage] = field(default_factory=deque)

    def record(self, run_usage: RunUsage) -> None:
        """Add usage and keep history for debugging."""
        self.usage.incr(run_usage)
        self.history.append(run_usage)
        # Limit history size to avoid unbounded memory growth
        max_history = 50
        if len(self.history) > max_history:
            self.history.popleft()

    def snapshot(self) -> RunUsage:
        """Return cumulative usage."""
        return self.usage
