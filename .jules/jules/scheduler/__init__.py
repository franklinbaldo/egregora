"""Scheduler package with legacy re-exports."""

from jules.scheduler.legacy import (  # noqa: F401
    JULES_BRANCH,
    JULES_SCHEDULER_PREFIX,
    check_schedule,
    ensure_jules_branch_exists,
    get_open_prs,
    get_pr_by_session_id_any_state,
    load_schedule_registry,
    prepare_session_base_branch,
    run_cycle_step,
)
from jules.core.client import JulesClient  # noqa: F401
