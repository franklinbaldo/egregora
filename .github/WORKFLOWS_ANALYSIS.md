# GitHub Workflows Analysis

> Generated: 2026-01-27

## Executive Summary

The repository has **7 workflow files** totaling **1,095 lines** of YAML. The workflows are generally well-structured with good documentation, but there are some areas of complexity and potential overlap.

### Workflow Inventory

| File | Lines | Purpose | Triggers |
|------|-------|---------|----------|
| `ci.yml` | 276 | Main CI pipeline | push, PR, schedule, dispatch |
| `jules.yml` | 223 | AI agent orchestration | PR closed, push, schedule, workflow_run, dispatch |
| `pr-conflict-label.yml` | 197 | PR conflict management | PR events, dispatch |
| `jules-pr.yml` | 157 | Jules PR automation | pull_request_target, workflow_run, dispatch |
| `docs-pages.yml` | 114 | Documentation deployment | push (main), dispatch |
| `cleanup.yml` | 81 | Artifact cleanup | weekly schedule, dispatch |
| `codeql.yml` | 47 | Security analysis | push, PR, weekly schedule, dispatch |

---

## Trigger Flow Diagram

```
                                    ┌─────────────────┐
                                    │   push (main)   │
                                    └────────┬────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
              ▼                              ▼                              ▼
     ┌────────────────┐            ┌─────────────────┐           ┌─────────────────┐
     │     ci.yml     │            │  docs-pages.yml │           │   codeql.yml    │
     │  (CI Pipeline) │            │  (Deploy Docs)  │           │ (Security Scan) │
     └────────┬───────┘            └─────────────────┘           └─────────────────┘
              │
              │ workflow_run (completed)
              ▼
     ┌────────────────┐
     │   jules.yml    │◄─────── schedule (*/15 * * * *)
     │  (Scheduler)   │◄─────── PR merged (Jules bot)
     └────────┬───────┘
              │
              │ Creates PR
              ▼
     ┌────────────────┐
     │  jules-pr.yml  │◄─────── pull_request_target (opened/sync)
     │  (Auto-merge)  │
     └────────┬───────┘
              │
              │ workflow_run (CI failure)
              ▼
     ┌────────────────┐
     │  Auto-fixer    │
     │  (in jules-pr) │
     └────────────────┘

     ┌────────────────┐
     │ pr-conflict-   │◄─────── pull_request (opened/sync)
     │ label.yml      │
     └────────────────┘

     ┌────────────────┐
     │  cleanup.yml   │◄─────── schedule (weekly)
     └────────────────┘
```

---

## Detailed Analysis by Workflow

### 1. ci.yml - Main CI Pipeline

**Purpose:** Core CI with linting, testing, security, and build.

**Jobs:**
- `pre-commit`: Runs pre-commit hooks
- `test-unit`: Unit tests with coverage
- `test-e2e`: End-to-end tests (30min timeout, `--cov-fail-under=45`)
- `security`: Safety, pip-audit, bandit scans
- `build`: Package build (depends on tests)
- `quality`: Radon, xenon, vulture (main/schedule only)
- `enable-auto-merge`: Status check for branch protection
- `summary`: Job result summary table

**Strengths:**
- Well-structured with proper dependencies
- Concurrency control (`cancel-in-progress: true`)
- Workflow dispatch inputs for debugging
- Artifact retention configured

**Issues:**
- `security` job has `continue-on-error: true` on bandit - failures might be silent
- `test-e2e` includes a specific step file (`test_reader_steps.py`) which seems odd

### 2. jules.yml - AI Agent Orchestration

**Purpose:** Orchestrates Jules AI agent sessions for automated maintenance.

**Jobs:**
- `on-merge`: Triggers scheduler when Jules PR merges
- `scheduler`: Main orchestration, picks persona, creates session
- `sync-main`: Merges jules branch into main

**Strengths:**
- Excellent inline documentation with flow diagrams
- State management via artifacts (avoids repo commits)
- Chain triggers for continuous automation

**Issues:**
- Complex trigger conditions (5 different events)
- Schedule runs every 15 minutes - potentially excessive
- `workflow_run` chains can be hard to debug

### 3. jules-pr.yml - Jules PR Automation

**Purpose:** Handles auto-merge and auto-fix for Jules PRs.

**Jobs:**
- `auto-merge`: Enables auto-merge for Jules PRs
- `auto-fixer`: Analyzes CI failures and triggers fixes

**Strengths:**
- Security-conscious (fork detection)
- Good separation of concerns
- Well-documented flow

**Issues:**
- `pull_request_target` is powerful/risky (documented but worth noting)
- Auto-fixer depends on external `repo.cli autofix` command

### 4. pr-conflict-label.yml - PR Conflict Management

**Purpose:** Labels PRs with conflicts and auto-updates branches.

**Jobs:**
- `manage-pr`: Checks mergeability, manages labels, updates branches

**Strengths:**
- Retry logic for mergeability status
- Triggers Jules for conflict resolution

**Issues:**
- **197 lines** is large for a labeling workflow
- Inline Python script (136-197) should be externalized
- Overlaps with `jules-pr.yml` in intent (both handle Jules PRs)

### 5. docs-pages.yml - Documentation Deployment

**Purpose:** Builds and deploys MkDocs documentation.

**Jobs:**
- `pages`: Build docs, demo site, repomix bundles, deploy

**Strengths:**
- Clean single-job design
- Uses GitHub Pages environment
- Generates repomix bundles for AI context

**Issues:**
- Node.js setup for just repomix - could use npx without setup-node

### 6. cleanup.yml - Artifact Cleanup

**Purpose:** Deletes artifacts older than 30 days.

**Jobs:**
- `cleanup`: Paginates through artifacts, deletes old ones

**Strengths:**
- Good summary reporting
- 10-minute timeout (safe)
- Weekly schedule appropriate

**Issues:**
- None significant

### 7. codeql.yml - Security Analysis

**Purpose:** GitHub CodeQL security scanning.

**Jobs:**
- `analyze`: Runs CodeQL on Python code

**Issues:**
- `upload: false` and `upload-database: false` - workflow runs but doesn't upload results
- Comment explains this is because "default setup" is enabled, making this workflow somewhat redundant

---

## Identified Patterns & Problems

### 1. Overlapping Triggers

| Trigger | Workflows Affected |
|---------|-------------------|
| `push` to main | ci.yml, docs-pages.yml, codeql.yml |
| `pull_request` | ci.yml, codeql.yml, pr-conflict-label.yml |
| `schedule` | ci.yml (daily), jules.yml (15min), cleanup.yml (weekly), codeql.yml (weekly) |
| `workflow_run` on CI | jules.yml, jules-pr.yml |

**Concern:** Both `jules.yml` and `jules-pr.yml` listen to CI completion via `workflow_run`. This could cause duplicate triggers.

### 2. Inline Code That Should Be Externalized

| Workflow | Lines | Location |
|----------|-------|----------|
| `pr-conflict-label.yml` | ~60 | Inline Python script (lines 136-197) |
| `cleanup.yml` | ~60 | Inline JavaScript (lines 22-81) |

### 3. Redundant Workflows

| Workflow | Concern |
|----------|---------|
| `codeql.yml` | Runs but doesn't upload results (GitHub default setup handles this) |

### 4. Schedule Frequency

| Workflow | Schedule | Concern |
|----------|----------|---------|
| `jules.yml` | Every 15 minutes | High frequency, potential cost/noise |
| `ci.yml` | Daily 3am | Appropriate |
| `cleanup.yml` | Weekly Sunday | Appropriate |
| `codeql.yml` | Weekly Monday | Appropriate |

### 5. Continue-on-error Usage

| Workflow | Job/Step | Risk |
|----------|----------|------|
| `ci.yml` | `security` job, bandit step | Security failures may go unnoticed |
| `jules.yml` | Download schedule state | Acceptable (has fallback) |
| `ci.yml` | xenon step | Minor (informational) |

---

## Recommendations

### High Priority

1. **Consider removing `codeql.yml`** - It runs but doesn't upload results. If GitHub's default CodeQL setup is enabled, this workflow is redundant and wastes compute time.

2. **Reduce Jules schedule frequency** - Every 15 minutes is aggressive. Consider 30 minutes or hourly. The `on-merge` trigger handles the primary loop.

3. **Externalize inline scripts**:
   - Move `pr-conflict-label.yml` Python to `.github/scripts/jules/trigger-conflict-fix.py`
   - Move `cleanup.yml` JavaScript to `.github/scripts/cleanup-artifacts.js`

### Medium Priority

4. **Review `workflow_run` listeners** - Both `jules.yml` and `jules-pr.yml` listen to CI completion. Ensure they have non-overlapping conditions to avoid duplicate work.

5. **Make bandit failures visible** - In `ci.yml`, either remove `continue-on-error` from bandit or add a follow-up step that warns about failures.

### Low Priority

6. **Remove `setup-node` from docs-pages.yml** - `npx repomix` works without it.

7. **Consider consolidating Jules workflows** - `jules.yml` and `jules-pr.yml` could potentially be one file with multiple jobs, reducing cognitive overhead.

---

## Supporting Files

### Scripts (`.github/scripts/`)

| Script | Used By |
|--------|---------|
| `jules/run-scheduler.sh` | jules.yml |
| `jules/restore-schedule-state.sh` | jules.yml |
| `jules/identify-pr.sh` | jules-pr.yml |
| `jules/enable-auto-merge.sh` | jules-pr.yml |
| `jules/sync-main.py` | jules.yml |
| `construct_gemini_prompt.py` | Not referenced in workflows (has tests but no workflow usage) |
| `analyze_historical_regressions.py` | Not referenced in any file (orphaned) |

### Composite Actions (`.github/actions/`)

| Action | Purpose |
|--------|---------|
| `setup-python-uv/action.yml` | Python + uv setup |
| `gemini-run/action.yml` | Gemini API runner |
| `shared-gemini-runner/action.yml` | Shared Gemini config |

---

## Cleanup Checklist

- [ ] Remove or disable `codeql.yml` if GitHub default setup is active
- [ ] Reduce `jules.yml` schedule from `*/15` to `*/30` or hourly
- [ ] Externalize inline Python in `pr-conflict-label.yml`
- [ ] Externalize inline JS in `cleanup.yml` (optional)
- [ ] Remove orphaned `analyze_historical_regressions.py` script
- [ ] Either use or remove `construct_gemini_prompt.py` (has tests but no workflow)
- [ ] Add visibility for bandit failures in `ci.yml`
- [ ] Document the `workflow_run` dependency chain
