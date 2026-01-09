"""Jules Scheduler - Compatibility layer.

This module re-exports utilities from scheduler_legacy for backward compatibility.
New code should use scheduler_v2.py for the main scheduler logic.
"""

# Re-export utilities that are still used by other modules and tests
from jules.client import JulesClient
from jules.github import get_open_prs, get_pr_by_session_id_any_state
from jules.scheduler_legacy import (
    CELEBRATION,
    IDENTITY_BRANDING,
    JOURNAL_MANAGEMENT,
    JULES_BRANCH,
    JULES_SCHEDULER_PREFIX,
    PRE_COMMIT_INSTRUCTIONS,
    SprintManager,
    check_schedule,
    ensure_jules_branch_exists,
    is_jules_drifted,
    load_schedule_registry,
    prepare_session_base_branch,
    rotate_drifted_jules_branch,
    run_cycle_step,
    sprint_manager,
    update_jules_from_main,
)

__all__ = [
    "CELEBRATION",
    "IDENTITY_BRANDING",
    "JOURNAL_MANAGEMENT",
    "JULES_BRANCH",
    "JULES_SCHEDULER_PREFIX",
    "JulesClient",
    "PRE_COMMIT_INSTRUCTIONS",
    "SprintManager",
    "check_schedule",
    "ensure_jules_branch_exists",
    "get_open_prs",
    "get_pr_by_session_id_any_state",
    "is_jules_drifted",
    "load_schedule_registry",
    "prepare_session_base_branch",
    "rotate_drifted_jules_branch",
    "run_cycle_step",
    "sprint_manager",
    "update_jules_from_main",
]