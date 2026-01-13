from jules.client import JulesClient
from jules.github import get_open_prs, get_pr_by_session_id_any_state
from jules.sprints import sprint_manager
from jules.resources.templates import (
    IDENTITY_BRANDING,
    JOURNAL_MANAGEMENT,
    CELEBRATION,
    PRE_COMMIT_INSTRUCTIONS,
)
from jules.scheduler_legacy import (
    JULES_BRANCH,
    JULES_SCHEDULER_PREFIX,
    check_schedule,
    ensure_jules_branch_exists,
    prepare_session_base_branch,
    run_cycle_step,
    update_jules_from_main,
    load_schedule_registry,
    load_prompt_entries,
)

# Re-exporting for compatibility with legacy consumers (if any)
__all__ = [
    "sprint_manager",
    "IDENTITY_BRANDING",
    "JOURNAL_MANAGEMENT",
    "CELEBRATION",
    "PRE_COMMIT_INSTRUCTIONS",
    "JULES_BRANCH",
    "JULES_SCHEDULER_PREFIX",
    "check_schedule",
    "ensure_jules_branch_exists",
    "prepare_session_base_branch",
    "run_cycle_step",
    "update_jules_from_main",
    "load_schedule_registry",
    "load_prompt_entries",
    "get_pr_by_session_id_any_state",
    "get_open_prs",
    "JulesClient",
]
