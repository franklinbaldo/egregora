from jules.sprints import sprint_manager
from jules.resources.templates import (
    IDENTITY_BRANDING,
    JOURNAL_MANAGEMENT,
    CELEBRATION,
    PRE_COMMIT_INSTRUCTIONS
)
from jules.scheduler_legacy import (
    JULES_BRANCH,
    JULES_SCHEDULER_PREFIX,
    ensure_jules_branch_exists,
    update_jules_from_main,
    load_schedule_registry,
    load_prompt_entries,
    check_schedule,
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
    "ensure_jules_branch_exists",
    "update_jules_from_main",
    "load_schedule_registry",
    "load_prompt_entries",
    "check_schedule",
]
