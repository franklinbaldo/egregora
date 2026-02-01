# GitHub Workflows Analysis

> Generated: 2026-01-27 | Oracle-First Stateless Architecture

## Executive Summary

The repository has **4 workflow files** totaling **~580 lines** of YAML.

**Architecture:** Oracle-First Stateless Scheduling
- Jules API is the single source of truth
- **Oracle facilitator unblocks stuck sessions FIRST**
- Then merges PRs and creates new sessions
- No CSV files, no artifacts, no external state

---

## Workflow Inventory

| File | Lines | Jobs | Purpose |
|------|-------|------|---------|
| `jules.yml` | ~270 | 5 | Complete Jules lifecycle (Oracle-first) |
| `ci.yml` | 157 | 5 | Main CI pipeline |
| `docs-pages.yml` | 106 | 1 | Documentation deployment |
| `cleanup.yml` | 81 | 1 | Artifact cleanup |

---

## Jules Workflow - Oracle-First Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  JULES ORACLE-FIRST SCHEDULER                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   TICK (every 15 min or on-merge):                                      │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ STEP 1: UNBLOCK STUCK SESSIONS (PRIMARY)                        │   │
│   │                                                                 │   │
│   │  Query API → Find AWAITING_USER_FEEDBACK sessions               │   │
│   │       │                                                         │   │
│   │       ▼                                                         │   │
│   │  For each stuck session:                                        │   │
│   │    ├── Extract question from activities                         │   │
│   │    ├── Get/create Oracle session (reusable)                     │   │
│   │    ├── Send question to Oracle                                  │   │
│   │    └── Send answer to stuck session → UNBLOCKED                 │   │
│   │                                                                 │   │
│   │  For AWAITING_PLAN_APPROVAL:                                    │   │
│   │    └── Auto-approve plan                                        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ STEP 2: MERGE COMPLETED PRS                                     │   │
│   │  └── Merge Jules PRs with admin override                        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ STEP 3: CREATE NEW SESSION                                      │   │
│   │  ├── Check for active sessions (skip if running)                │   │
│   │  ├── Check CI on main (fixer if failing)                        │   │
│   │  └── Round-robin through personas                               │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Oracle Facilitator

### Purpose

When a Jules session gets stuck waiting for user input (`AWAITING_USER_FEEDBACK`),
the Oracle automatically:
1. Extracts the question from session activities
2. Routes it to a reusable Oracle session
3. Sends guidance back to unblock the stuck session

### Session States Handled

| State | Action |
|-------|--------|
| `AWAITING_USER_FEEDBACK` | Extract question → Oracle → Unblock |
| `AWAITING_PLAN_APPROVAL` | Auto-approve plan |
| `IN_PROGRESS` | Skip (actively running) |
| `COMPLETED` | Skip (done) |
| `FAILED` | Skip (terminal) |

### Oracle Session

- **Title Pattern:** `🔮 oracle {repo}`
- **Reused:** Yes (one per repo, not recreated each tick)
- **Mode:** `MANUAL` (doesn't create PRs)
- **Role:** Technical support for other personas

---

## State Sources

| What | Source | NOT |
|------|--------|-----|
| Stuck sessions | Jules API `list_sessions()` state=AWAITING_* | - |
| Question text | Jules API `get_activities()` | - |
| Active sessions | Jules API `list_sessions()` state=IN_PROGRESS | CSV |
| Last persona | Jules API session titles | CSV |
| Next persona | Round-robin from `.team/personas/` | CSV |

---

## Jobs

| Job | Trigger | Purpose |
|-----|---------|---------|
| `on-merge` | Jules PR merged to main | Triggers scheduler |
| `scheduler` | cron/dispatch/workflow_run | Oracle-first tick |
| `auto-merge` | pull_request_target | Enable auto-merge |
| `auto-fixer` | CI failure | Analyze and fix |

---

## Key Functions

### Oracle Facilitator (`stateless.py`)

| Function | Purpose |
|----------|---------|
| `get_stuck_sessions()` | Find sessions in AWAITING_* states |
| `extract_question_from_session()` | Get question from activities |
| `get_or_create_oracle_session()` | Reusable Oracle session |
| `facilitate_stuck_session()` | Route question and unblock |
| `unblock_stuck_sessions()` | Main orchestration |

### Regular Scheduling (`stateless.py`)

| Function | Purpose |
|----------|---------|
| `discover_personas()` | List available personas |
| `get_active_session()` | Check for running sessions |
| `get_last_persona_from_api()` | Find last persona |
| `get_next_persona()` | Round-robin calculation |
| `run_scheduler()` | Main entry point |

---

## Benefits

1. **No stuck sessions** - Oracle automatically unblocks waiting sessions
2. **No wasted time** - Sessions don't sit waiting for human input
3. **Reusable Oracle** - One Oracle session handles all questions
4. **Stateless** - API is source of truth, no CSV drift
5. **Self-healing** - Auto-approves plans, auto-fixes CI

---

## Scripts (`.github/scripts/jules/`)

| Script | Purpose |
|--------|---------|
| `enable-auto-merge.sh` | Enable auto-merge on PR |
| `identify-pr.sh` | Find PR from workflow_run |
