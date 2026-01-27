# GitHub Workflows Analysis

> Generated: 2026-01-27 | Updated after unification

## Executive Summary

The repository has **4 workflow files** totaling **654 lines** of YAML.

**Consolidation History:**
1. Removed `codeql.yml` (redundant - GitHub default setup active)
2. Removed `pr-conflict-label.yml` (197 lines of inline code)
3. Simplified `ci.yml` from 8 jobs to 5 jobs
4. **Unified `jules.yml` and `jules-pr.yml`** into single workflow

**Result:** 40% reduction in workflow code (1,095 → 654 lines)

---

## Workflow Inventory

| File | Lines | Jobs | Purpose |
|------|-------|------|---------|
| `jules.yml` | 310 | 5 | Complete Jules lifecycle (scheduler, auto-merge, auto-fix) |
| `ci.yml` | 157 | 5 | Main CI pipeline |
| `docs-pages.yml` | 106 | 1 | Documentation deployment |
| `cleanup.yml` | 81 | 1 | Artifact cleanup |

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
              │ (success)                                     (failure)     │
              ▼                                                             ▼
     ┌─────────────────────────────────────────────────────────────────────────┐
     │                            jules.yml                                    │
     │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
     │  │  scheduler  │  │  sync-main  │  │  auto-merge │  │   auto-fixer    │ │
     │  │ (every 15m) │  │             │  │             │  │  (on CI fail)   │ │
     │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │
     │         │                                   ▲                           │
     │         │ creates PR                        │ pull_request_target       │
     │         └───────────────────────────────────┘                           │
     │                                                                         │
     │  ┌─────────────┐                                                        │
     │  │  on-merge   │◄─────── PR merged by Jules                             │
     │  └──────┬──────┘                                                        │
     │         │ triggers scheduler                                            │
     │         └──────────────────────────────────────────────────────────────►│
     └─────────────────────────────────────────────────────────────────────────┘

     ┌────────────────┐
     │  cleanup.yml   │◄─────── schedule (weekly)
     └────────────────┘
```

---

## Detailed Analysis

### 1. jules.yml - Unified Jules Workflow (310 lines)

**Purpose:** Complete Jules AI agent lifecycle management.

**Jobs (5 total):**
| Job | Trigger | Purpose |
|-----|---------|---------|
| `on-merge` | PR merged by Jules | Triggers scheduler for next session |
| `scheduler` | dispatch, schedule (15m), workflow_run (success) | Picks persona, creates session |
| `sync-main` | After scheduler | Merges jules → main |
| `auto-merge` | pull_request_target | Enables auto-merge on Jules PRs |
| `auto-fixer` | workflow_run (failure), dispatch | Analyzes CI failures, triggers fixes |

**Optimizations Applied:**
- Sparse checkout for scheduler (faster ticks)
- 5-minute timeout on scheduler
- Unified workflow_dispatch inputs

**Security:**
- `pull_request_target` fork check in auto-merge job
- Per-PR concurrency for auto-merge

### 2. ci.yml - Main CI Pipeline (157 lines)

**Jobs (5 total):**
| Job | Timeout | Purpose |
|-----|---------|---------|
| `pre-commit` | 10min | Linting, formatting |
| `test-unit` | 10min | Unit tests with coverage |
| `test-e2e` | 30min | E2E tests, 45% coverage threshold |
| `security` | 10min | Safety + pip-audit |
| `build` | 5min | Package build |

### 3. docs-pages.yml - Documentation (106 lines)

**Single Job:** Build docs, demo site, repomix bundles, deploy to Pages.

### 4. cleanup.yml - Artifact Cleanup (81 lines)

**Single Job:** Weekly cleanup of artifacts older than 30 days.

---

## Metrics

| Metric | Original | After Cleanup | After Unification | Total Change |
|--------|----------|---------------|-------------------|--------------|
| Workflow files | 7 | 5 | **4** | -43% |
| Total lines | 1,095 | 724 | **654** | **-40%** |
| Jules-related files | 2 | 2 | **1** | -50% |
| Jules jobs | 5 | 5 | **5** | 0 |

---

## Cleanup Checklist

### Completed

- [x] Remove redundant `codeql.yml`
- [x] Remove `pr-conflict-label.yml`
- [x] Simplify CI workflow (8 → 5 jobs)
- [x] Remove duplicate bundle artifact upload
- [x] Streamline pre-commit hooks
- [x] Optimize scheduler tick (sparse checkout)
- [x] **Unify Jules workflows into single file**

### Remaining

- [ ] Remove orphaned `analyze_historical_regressions.py` script
- [ ] Either use or remove `construct_gemini_prompt.py`
- [ ] Make security scan failures visible (remove `|| true`)

---

## Supporting Files

### Scripts (`.github/scripts/jules/`)

| Script | Used By | Purpose |
|--------|---------|---------|
| `run-scheduler.sh` | jules.yml | Main scheduler execution |
| `restore-schedule-state.sh` | jules.yml | Restore state from artifact |
| `identify-pr.sh` | jules.yml | Find PR from workflow_run event |
| `enable-auto-merge.sh` | jules.yml | Enable auto-merge on PR |
| `sync-main.py` | jules.yml | Merge jules → main |

### Composite Actions (`.github/actions/`)

| Action | Purpose |
|--------|---------|
| `setup-python-uv/action.yml` | Python + uv setup |
| `gemini-run/action.yml` | Gemini API runner |
| `shared-gemini-runner/action.yml` | Shared Gemini config |
