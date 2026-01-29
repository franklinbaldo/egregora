# Investigation: causaganha System Degraded

**Date**: 2026-01-29
**Dashboard**: https://franklinbaldo.github.io/causaganha/
**Status observed**: Degradado (Degraded)

---

## Summary

The causaganha Pipeline Monitor dashboard reports "Degradado" status because the
**Jules Scheduler** workflow fails consistently every 5 minutes, while the
**Data Pipeline** workflow succeeds. Since the dashboard calculates system health
from the last 10 GitHub Actions runs (>=80% success = Operacional, >=50% = Degradado,
<50% = Falha), the ~50% failure rate puts the system in degraded state.

---

## Root Cause Analysis

### Primary Cause: Empty `schedule.csv`

**File**: `.team/schedule.csv`
**Current content**: Headers only, no data rows.

```csv
sequence,persona,session_id,pr_number,pr_status,base_commit
```

The `execute_sequential_tick()` function in `.team/repo/scheduler/engine.py` loads
the schedule and returns immediate failure when no rows exist:

```python
rows = load_schedule()
if not rows:
    return SchedulerResult(
        success=False,
        message=f"No schedule found at {SCHEDULE_PATH}",
    )
```

The auto-extend feature (`auto_extend()`) only triggers when there are already
rows in the schedule but the remaining empty slots fall below a threshold. **There
is no bootstrapping mechanism** to create initial rows when the schedule is
completely empty.

**Origin**: The schedule was likely emptied during the Jan 20 commit
`7cd8385 chore: reset personas to start fresh - clear journals and mail` and
was never repopulated.

### Secondary Cause: Governance [PLEAD] Mismatch

Even if the schedule had data, the scheduler would still fail due to the
governance check in `execute_sequential_tick()`:

```python
from repo.features.governance import GovernanceManager
gov = GovernanceManager()
if not gov.is_persona_pleaded(persona_id):
    return SchedulerResult(
        success=False,
        message=f"Persona '{persona_id}' not pleaded to Constitution",
    )
```

The `is_persona_pleaded()` method searches for **git commit messages** starting
with `[PLEAD] {persona_id}` on commits touching `CONSTITUTION.md`. However,
the 28 persona pledges exist only as **file content** within `CONSTITUTION.md`,
not as separate commits with `[PLEAD]` prefixed messages.

Git log for CONSTITUTION.md shows only 2 commits:
1. `134c2f5` - "feat: integrate Jules automation system from egregora" (Jan 20)
2. `fa0d3d3` - "style: apply ruff formatting and linting fixes" (Jan 22)

Neither has a `[PLEAD]` prefix, so `is_persona_pleaded()` returns `False` for
all personas.

---

## Failure Flow

```
GitHub Actions (cron: */5 * * * *)
  └─ jules_scheduler.yml
       └─ Step: "Run Jules Scheduler"
            └─ uv run python -m repo.cli schedule tick
                 └─ run_scheduler()
                      ├─ execute_facilitator_tick()      # runs
                      ├─ execute_sequential_tick()        # FAILS: "No schedule found"
                      ├─ pr_mgr.reconcile_all_jules_prs() # still runs
                      ├─ update_schedule_pr_status()      # still runs
                      ├─ poller.poll_and_deliver()         # still runs
                      └─ run_sync()                        # still runs
                      └─ returns SchedulerResult(success=False)
                 └─ CLI: typer.Exit(code=1)
            └─ Step exit code: 1 → FAILURE
```

Steps 3-6 in `run_scheduler()` still execute even after the sequential tick
fails, explaining the ~31 second runtime before the failure is reported.

---

## Impact

| Workflow | Frequency | Status | Effect |
|----------|-----------|--------|--------|
| Data Pipeline | ~10 min | Always succeeds | Healthy |
| Jules Scheduler | 5 min | Always fails | Degrades dashboard |
| vendor-pje-swagger.yml | On trigger | Recent failure | Minor |

The Jules Scheduler runs twice as frequently as the Data Pipeline, so its
failures dominate the recent runs window, keeping the dashboard in "Degradado"
or worse.

---

## Recommended Fixes

### Fix 1: Bootstrap the schedule (immediate)

Add initial persona rows to `schedule.csv` or implement a bootstrapping
mechanism in `execute_sequential_tick()`:

```python
rows = load_schedule()
if not rows:
    # Bootstrap: create initial schedule from available personas
    rows = bootstrap_schedule_from_personas(PERSONA_DIR)
    if rows and not dry_run:
        save_schedule(rows)
    if not rows:
        return SchedulerResult(
            success=False,
            message=f"No schedule found at {SCHEDULE_PATH}",
        )
```

### Fix 2: Create [PLEAD] commits for active personas

For each active persona, create a commit touching `CONSTITUTION.md` with the
message format `[PLEAD] {persona_id}: I agree to the Constitution`. Or modify
`is_persona_pleaded()` to also check file content:

```python
def is_persona_pleaded(self, persona_id: str) -> bool:
    # Check commit messages first
    if self.get_persona_last_plead_commit(persona_id) != "":
        return True
    # Fall back to checking file content
    if self.constitution_path.exists():
        content = self.constitution_path.read_text()
        return f"[PLEAD] {persona_id}" in content
    return False
```

### Fix 3: Fail gracefully in scheduler (reduce noise)

Change `run_scheduler()` to not return failure when the schedule is simply
empty but other operations succeed:

```python
if persona_id:
    result = execute_single_persona(persona_id, dry_run)
else:
    result = execute_sequential_tick(dry_run, reset)

# Don't fail the whole run if schedule is just empty
if not result.success and "No schedule found" in result.message:
    result = SchedulerResult(success=True, message="Schedule empty, skipping tick")
```

### Fix 4: Reduce scheduler frequency

The `*/5 * * * *` cron (every 5 minutes) is aggressive. If the scheduler has
no work, running this often just generates noise. Consider `*/15 * * * *` or
`*/30 * * * *`.

---

## Files Involved

| File | Role |
|------|------|
| `.team/schedule.csv` | Empty schedule (root cause) |
| `.team/repo/scheduler/engine.py` | Scheduler logic, `run_scheduler()` |
| `.team/repo/cli/main.py` | CLI entry point, `schedule_tick()` |
| `.team/repo/features/governance.py` | `GovernanceManager.is_persona_pleaded()` |
| `.team/CONSTITUTION.md` | Governance document with pledges as content |
| `.github/workflows/jules_scheduler.yml` | Workflow definition (cron: */5) |
