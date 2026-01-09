"""Jules Scheduler - Compatibility layer.

This module re-exports utilities from scheduler_legacy for backward compatibility.
New code should use scheduler_v2.py for the main scheduler logic.
"""

# Re-export utilities that are still used by other modules
from jules.scheduler_legacy import (
    JULES_BRANCH,
    JULES_SCHEDULER_PREFIX,
    SprintManager,
    check_schedule,
    load_schedule_registry,
    sprint_manager,
)

__all__ = [
    "JULES_BRANCH",
    "JULES_SCHEDULER_PREFIX",
    "SprintManager",
    "check_schedule",
    "load_schedule_registry",
    "sprint_manager",
]
