# GitHub Workflows Analysis

> Generated: 2026-01-27 | Updated after cleanup

## Executive Summary

The repository has **5 workflow files** totaling **724 lines** of YAML.

**Recent Cleanup (Commits 70211d3 → 3dd033c):**
- Removed `codeql.yml` (redundant - GitHub default setup active)
- Removed `pr-conflict-label.yml` (197 lines of inline code)
- Simplified `ci.yml` from 8 jobs to 5 jobs (276 → 157 lines)
- Removed duplicate bundle artifact upload from `docs-pages.yml`
- Streamlined pre-commit hooks (removed bandit)

**Result:** 34% reduction in workflow code (1,095 → 724 lines)

---

## Workflow Inventory

| File | Lines | Purpose | Triggers |
|------|-------|---------|----------|
| `jules.yml` | 223 | AI agent orchestration | PR closed, push, schedule (15min), workflow_run, dispatch |
| `ci.yml` | 157 | Main CI pipeline | push, PR, dispatch |
| `jules-pr.yml` | 157 | Jules PR automation | pull_request_target, workflow_run, dispatch |
| `docs-pages.yml` | 106 | Documentation deployment | push (main), dispatch |
| `cleanup.yml` | 81 | Artifact cleanup | weekly schedule, dispatch |

---

## Trigger Flow Diagram

```
                                    ┌─────────────────┐
                                    │   push (main)   │
                                    └────────┬────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
              ▼                              ▼                              │
     ┌────────────────┐            ┌─────────────────┐                      │
     │     ci.yml     │            │  docs-pages.yml │                      │
     │  (CI Pipeline) │            │  (Deploy Docs)  │                      │
     └────────┬───────┘            └─────────────────┘                      │
              │                                                             │
              │ workflow_run                                                │
              ├─────────────────────────────────────────────────────────────┤
              │ (completed)                                   (failure)     │
              ▼                                                             ▼
     ┌────────────────┐                                          ┌─────────────────┐
     │   jules.yml    │◄─────── schedule (*/15 * * * *)          │  jules-pr.yml   │
     │  (Scheduler)   │◄─────── PR merged (Jules bot)            │  (Auto-fixer)   │
     └────────┬───────┘                                          └─────────────────┘
              │
              │ Creates PR
              ▼
     ┌────────────────┐
     │  jules-pr.yml  │◄─────── pull_request_target (opened/sync)
     │  (Auto-merge)  │
     └────────────────┘

     ┌────────────────┐
     │  cleanup.yml   │◄─────── schedule (weekly)
     └────────────────┘
```

---

## Detailed Analysis by Workflow

### 1. ci.yml - Main CI Pipeline (157 lines)

**Purpose:** Core CI with linting, testing, security, and build.

**Jobs (5 total):**
| Job | Timeout | Dependencies | Purpose |
|-----|---------|--------------|---------|
| `pre-commit` | 10min | none | Linting, formatting |
| `test-unit` | 10min | none | Unit tests with coverage |
| `test-e2e` | 30min | none | E2E tests, 45% coverage threshold |
| `security` | 10min | none | Safety + pip-audit |
| `build` | 5min | pre-commit, test-unit, test-e2e | Package build |

**Strengths:**
- Well-documented with header comments
- Concurrency control (`cancel-in-progress: true`)
- Skip tests option for debugging
- Proper job dependencies for build

**Remaining Issues:**
- `security` job uses `|| true` - failures are silent
- `test_reader_steps.py` included in e2e tests seems out of place

### 2. jules.yml - AI Agent Orchestration (223 lines)

**Purpose:** Orchestrates Jules AI agent sessions for automated maintenance.

**Jobs (3 total):**
| Job | Trigger Condition | Purpose |
|-----|-------------------|---------|
| `on-merge` | PR merged by Jules | Triggers scheduler for next session |
| `scheduler` | dispatch, schedule, workflow_run | Picks persona, creates session |
| `sync-main` | After scheduler | Merges jules branch into main |

**Strengths:**
- Excellent inline documentation with ASCII flow diagrams
- State management via artifacts (avoids repo commits)
- Chain triggers for continuous automation

**Remaining Issues:**
- Schedule runs every 15 minutes - potentially excessive
- 5 different event types makes debugging complex

### 3. jules-pr.yml - Jules PR Automation (157 lines)

**Purpose:** Handles auto-merge and auto-fix for Jules PRs.

**Jobs (2 total):**
| Job | Trigger | Purpose |
|-----|---------|---------|
| `auto-merge` | pull_request_target | Enable auto-merge for Jules PRs |
| `auto-fixer` | CI failure, dispatch | Analyze failures, trigger fixes |

**Strengths:**
- Security-conscious (fork detection prevents secret exposure)
- Well-documented security notes
- Sparse checkout for efficiency

**Notes:**
- Uses `pull_request_target` (powerful/risky, but properly guarded)

### 4. docs-pages.yml - Documentation Deployment (106 lines)

**Purpose:** Builds and deploys MkDocs documentation.

**Single Job:** `pages`
- Builds MkDocs documentation
- Generates demo site with real Gemini API (if available)
- Creates repomix bundles for AI context
- Deploys to GitHub Pages

**Strengths:**
- Clean single-job design
- Graceful fallback when Gemini API unavailable
- Build metadata injected into mkdocs.yml

### 5. cleanup.yml - Artifact Cleanup (81 lines)

**Purpose:** Deletes artifacts older than 30 days.

**Single Job:** `cleanup`
- Weekly schedule (Sunday 3am UTC)
- Paginates through all artifacts
- Provides summary of cleaned items

**Status:** Well-designed, no issues.

---

## Current State Assessment

### What Was Fixed

| Issue | Resolution |
|-------|------------|
| Redundant `codeql.yml` | Removed (GitHub default setup active) |
| 197-line inline Python in `pr-conflict-label.yml` | Entire workflow removed |
| 8 jobs in CI | Reduced to 5 jobs |
| Duplicate artifact uploads | Removed from docs-pages |
| Bandit in pre-commit | Removed (was causing friction) |

### Remaining Recommendations

#### Medium Priority

1. **Reduce Jules schedule frequency** - Every 15 minutes is aggressive. Consider 30 minutes or hourly. The `on-merge` trigger handles the primary loop.

2. **Make security failures visible** - In `ci.yml`, the security job uses `|| true` which hides failures. Consider:
   ```yaml
   - name: Check dependencies for vulnerabilities
     run: |
       uvx safety check --full-report
       uvx pip-audit
     continue-on-error: true  # Visible failure without blocking
   ```

3. **Review `workflow_run` listeners** - Both `jules.yml` and `jules-pr.yml` listen to CI completion. Ensure they have non-overlapping conditions.

#### Low Priority

4. **Document the test file inclusion** - `test_reader_steps.py` in e2e tests looks like it might be step definitions (BDD), worth a comment.

5. **Consider consolidating Jules workflows** - `jules.yml` and `jules-pr.yml` could potentially be one file, reducing cognitive overhead.

---

## Supporting Files

### Scripts (`.github/scripts/jules/`)

| Script | Used By | Purpose |
|--------|---------|---------|
| `run-scheduler.sh` | jules.yml | Main scheduler execution |
| `restore-schedule-state.sh` | jules.yml | Restore state from artifact |
| `identify-pr.sh` | jules-pr.yml | Find PR from workflow_run event |
| `enable-auto-merge.sh` | jules-pr.yml | Enable auto-merge on PR |
| `sync-main.py` | jules.yml | Merge jules → main |

### Potentially Unused Scripts

| Script | Status |
|--------|--------|
| `construct_gemini_prompt.py` | Has tests but no workflow reference |
| `analyze_historical_regressions.py` | Not referenced anywhere (orphaned) |

### Composite Actions (`.github/actions/`)

| Action | Purpose |
|--------|---------|
| `setup-python-uv/action.yml` | Python + uv setup |
| `gemini-run/action.yml` | Gemini API runner |
| `shared-gemini-runner/action.yml` | Shared Gemini config |

---

## Cleanup Checklist

### Completed

- [x] Remove redundant `codeql.yml`
- [x] Remove `pr-conflict-label.yml` (externalize or delete inline code)
- [x] Simplify CI workflow (8 → 5 jobs)
- [x] Remove duplicate bundle artifact upload
- [x] Streamline pre-commit hooks

### Remaining

- [ ] Reduce `jules.yml` schedule from `*/15` to `*/30` or hourly
- [ ] Remove orphaned `analyze_historical_regressions.py` script
- [ ] Either use or remove `construct_gemini_prompt.py`
- [ ] Make security scan failures visible (remove `|| true`)
- [ ] Document `workflow_run` dependency chain

---

## Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Workflow files | 7 | 5 | -29% |
| Total lines | 1,095 | 724 | -34% |
| CI jobs | 8 | 5 | -38% |
| Inline scripts | 2 | 0 | -100% |
