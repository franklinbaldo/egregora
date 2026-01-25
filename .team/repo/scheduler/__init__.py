"""Jules Scheduler Package.

This package provides a simplified scheduler for Jules persona execution.
The scheduler:
1. Merges completed Jules PRs (drafts that pass CI)
2. Finds the next persona (round-robin from API state)
3. Renders the persona prompt with Jinja2
4. Creates a Jules session

Usage:
    from repo.scheduler import run_scheduler
    result = run_scheduler()
"""

# Main scheduler exports
from repo.scheduler.simple import (  # noqa: F401
    SchedulerResult,
    discover_personas,
    merge_completed_prs,
    run_scheduler,
)

# Keep some legacy exports for compatibility during transition
from repo.scheduler.legacy import JULES_BRANCH  # noqa: F401
