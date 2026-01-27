# GitHub Workflows Analysis

> Generated: 2026-01-27 | Stateless architecture

## Executive Summary

The repository has **4 workflow files** totaling **~580 lines** of YAML.

**Architecture:** Ralph Wiggum style stateless scheduling
- Jules API is the single source of truth
- No CSV files, no artifacts, no external state
- Each tick queries API, derives next action, executes

---

## Workflow Inventory

| File | Lines | Jobs | Purpose |
|------|-------|------|---------|
| `jules.yml` | ~270 | 5 | Complete Jules lifecycle (stateless) |
| `ci.yml` | 157 | 5 | Main CI pipeline |
| `docs-pages.yml` | 106 | 1 | Documentation deployment |
| `cleanup.yml` | 81 | 1 | Artifact cleanup |

---

## Jules Workflow - Stateless Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     JULES STATELESS LOOP                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   TICK (every 15 min or on-merge):                                      │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ 1. Query Jules API: any active sessions?                        │   │
│   │    → YES: skip (already running)                                │   │
│   │    → NO: continue                                               │   │
│   │                                                                 │   │
│   │ 2. Merge any completed Jules PRs (admin override)               │   │
│   │                                                                 │   │
│   │ 3. Query Jules API: what was last persona?                      │   │
│   │                                                                 │   │
│   │ 4. Calculate next persona (round-robin from filesystem)         │   │
│   │                                                                 │   │
│   │ 5. Create new Jules session via API                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   Jules works asynchronously, creates PR                                │
│                              ↓                                          │
│   AUTO-MERGE enables auto-merge on PR                                   │
│                              ↓                                          │
│   CI runs                                                               │
│         ├── SUCCESS → PR merges → ON-MERGE triggers next tick           │
│         └── FAILURE → AUTO-FIXER sends fix instructions to Jules        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### State Sources

| What | Source | NOT |
|------|--------|-----|
| Active sessions | Jules API `list_sessions()` | CSV |
| Last persona | Jules API session titles | CSV |
| Next persona | Round-robin from `.team/personas/` | CSV |
| PR status | GitHub API | CSV |

### Jobs

| Job | Trigger | Purpose |
|-----|---------|---------|
| `on-merge` | Jules PR merged | Triggers scheduler |
| `scheduler` | cron/dispatch/workflow_run | Query API, create session |
| `sync-main` | After scheduler | Merge jules → main |
| `auto-merge` | pull_request_target | Enable auto-merge |
| `auto-fixer` | CI failure | Analyze and fix |

---

## Removed (Dead Code Cleanup)

| Item | Reason |
|------|--------|
| `schedule.csv` | Replaced by Jules API |
| `oracle_schedule.csv` | Unused |
| `restore-schedule-state.sh` | CSV artifact handling |
| `run-scheduler.sh` | Replaced by direct CLI call |
| `schedule.py` | Old CSV-based scheduler |
| `test_csv_scheduler.py` | Tests for removed code |
| CSV artifact upload/download | No longer needed |

---

## Scripts (`.github/scripts/jules/`)

| Script | Purpose |
|--------|---------|
| `enable-auto-merge.sh` | Enable auto-merge on PR |
| `identify-pr.sh` | Find PR from workflow_run |
| `sync-main.py` | Merge jules → main |

---

## Scheduler Code

**Location:** `.team/repo/scheduler/stateless.py`

Key functions:
- `get_active_session()` - Query API for running sessions
- `get_last_persona_from_api()` - Find last persona from session titles
- `get_next_persona()` - Round-robin calculation
- `merge_completed_prs()` - Merge Jules PRs with admin override
- `run_scheduler()` - Main entry point

---

## Benefits of Stateless Architecture

1. **No state drift** - API is always authoritative
2. **No merge conflicts** - No CSV to conflict
3. **Simpler workflow** - No artifact handling
4. **Faster ticks** - No download/upload steps
5. **Debuggable** - Query API to see current state
6. **Ralph Wiggum style** - Iteration > perfection
