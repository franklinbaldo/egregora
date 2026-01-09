# Jules Scheduler Diagnostic Notes

## Issue Summary
The Jules scheduler is repeating the same persona (curator) instead of advancing through the cycle.

## Evidence
1. **Multiple scheduler base branches for curator only:**
   - `jules-sched-curator-main-202601082201`
   - `jules-sched-curator-main-202601082202`
   - `jules-sched-curator-main-202601082203`
   - ...continuing through `jules-sched-curator-main-202601082335`

2. **Jules HAS created PRs for curator:**
   - `curator/ux-audit-and-planning-3655817757514838229`
   - `curator-ux-audit-and-planning-16244347034986588289`
   - Multiple other curator branches exist

3. **Other personas have been run successfully in the past:**
   - `refactor/phase1-core-merge-1939829467892166746` (merged to main)
   - `visionary-symbiote-rfcs-18137872022314526283`
   - `sheriff-fix-vulture-whitelist-path-5099007441331269247` (PR #2279)

## Code Analysis

### Session Matching Logic
The scheduler uses `get_last_cycle_session()` to find the most recent session:
1. Lists all Jules sessions (sorted by creation time)
2. For each session, tries to find its PR
3. Checks if PR's `baseRefName` starts with "jules-sched-"
4. Extracts persona ID from base branch name
5. Returns the first match

### Verified Working Components
- ✅ Persona matching from branch names works correctly
- ✅ Session ID extraction from branch names works correctly
- ✅ Jules creates branches and PRs successfully
- ✅ Scheduler creates base branches correctly

### Root Cause: Branch Override in Persona Configs ✅ FIXED
**FOUND AND FIXED**: The persona frontmatter contained `branch: "main"` which was overriding the scheduler's dynamically-created base branch parameter.

**Expected flow:**
1. Scheduler creates `jules-sched-curator-main-202601082335`
2. Scheduler calls `client.create_session(branch="jules-sched-curator-main-202601082335", ...)`
3. Jules creates PR from `curator/ux-audit-...` → `jules-sched-curator-main-202601082335`
4. Next scheduler tick finds PR with `baseRefName="jules-sched-curator-main-202601082335"`
5. Scheduler merges PR and advances to next persona

**Actual behavior (before fix):**
- Persona config had `branch: "main"` in frontmatter
- Jules used the persona's branch config instead of the scheduler's parameter
- PRs targeted `main` instead of `jules-sched-*` branches
- `get_last_cycle_session()` couldn't find PRs (baseRefName filter failed on "main")
- Scheduler defaulted to starting fresh with curator again

**Fix Applied (commit 1b01224):**
Removed `branch: "main"` from all 23 persona configurations. In cycle mode, the scheduler must have full control over the base branch to enable proper session tracking and persona advancement.

## Testing Steps
1. Trigger scheduler in CI (has GitHub token and Jules API access)
2. Check workflow logs to see:
   - What base branch is passed to Jules
   - What PRs are returned by `get_open_prs()`
   - What `get_last_cycle_session()` returns
3. Manually check a curator PR to verify its `baseRefName`

## Recent Fix
Commit `0a9e422` changed persona matching from `headRefName` to `baseRefName`, which was correct, but the underlying issue of PRs not having the right base might remain.
