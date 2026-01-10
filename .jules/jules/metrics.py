"""Simple metrics tracking for Jules scheduler."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class TickMetrics:
    """Metrics for a single scheduler tick."""

    tick_time: str  # ISO timestamp
    mode: str  # "cycle" or "scheduled"

    # Cycle mode fields
    last_persona_id: str | None = None
    next_persona_id: str | None = None
    pr_number: int | None = None
    pr_merged: bool = False
    sprint_incremented: bool = False

    # Errors
    error: str | None = None

    # Session created
    session_id: str | None = None
    session_persona: str | None = None


class MetricsCollector:
    """Collects and persists scheduler metrics."""

    METRICS_DIR = Path(".jules/metrics")
    METRICS_FILE = METRICS_DIR / "ticks.jsonl"

    def __init__(self):
        self.METRICS_DIR.mkdir(parents=True, exist_ok=True)

    def record_tick(self, metrics: TickMetrics):
        """Append tick metrics to JSONL file."""
        with open(self.METRICS_FILE, "a") as f:
            f.write(json.dumps(asdict(metrics)) + "\n")

    def get_recent_ticks(self, n: int = 100) -> list[TickMetrics]:
        """Read last N ticks from metrics file."""
        if not self.METRICS_FILE.exists():
            return []

        with open(self.METRICS_FILE, "r") as f:
            lines = f.readlines()

        ticks = []
        for line in lines[-n:]:
            data = json.loads(line)
            ticks.append(TickMetrics(**data))

        return ticks

    def get_stats(self, last_n_ticks: int = 100) -> dict:
        """Calculate statistics from recent ticks."""
        ticks = self.get_recent_ticks(last_n_ticks)

        if not ticks:
            return {"error": "No ticks recorded"}

        total = len(ticks)
        errors = sum(1 for t in ticks if t.error)
        merges = sum(1 for t in ticks if t.pr_merged)
        sessions = sum(1 for t in ticks if t.session_id)
        sprints = sum(1 for t in ticks if t.sprint_incremented)

        # Count personas
        persona_counts = {}
        for tick in ticks:
            if tick.session_persona:
                persona_counts[tick.session_persona] = persona_counts.get(tick.session_persona, 0) + 1

        return {
            "total_ticks": total,
            "errors": errors,
            "error_rate": f"{errors/total*100:.1f}%",
            "prs_merged": merges,
            "sessions_created": sessions,
            "sprints_completed": sprints,
            "most_run_persona": max(persona_counts.items(), key=lambda x: x[1]) if persona_counts else None,
            "unique_personas": len(persona_counts),
        }
