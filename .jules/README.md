# Jules Automation System

This directory contains the Jules automation infrastructure for Egregora, including AI agent personas, scheduler configuration, and sprint planning.

## 📁 Directory Structure

```
.jules/
├── jules/              # Scheduler implementation
│   ├── cli/            # Typer CLIs (main, mail, job, my-tools)
│   ├── core/           # API clients + shared exceptions
│   ├── features/       # Autofix, feedback, mail, polling, sessions, sprints
│   ├── scheduler/      # Engine, legacy compatibility, managers, state
│   ├── templates/      # Prompt templates, blocks, partials
│   └── resources/      # Placeholder for scheduler resources (currently empty)
│
├── personas/           # AI agent persona definitions
│   ├── curator/        # 🎭 UX/UI evaluation
│   ├── refactor/       # 🔧 Code quality
│   ├── visionary/      # 🔮 Strategic moonshots
│   ├── bolt/           # ⚡ Performance optimization
│   ├── sentinel/       # 🛡️ Security audits
│   ├── builder/        # 🏗️ Data architecture
│   ├── shepherd/       # 🧑‍🌾 Test coverage
│   ├── janitor/        # 🧹 Code hygiene
│   ├── docs_curator/   # 📚 Documentation gardening
│   ├── artisan/        # 🔨 Code craftsmanship
│   ├── palette/        # 🎨 Design system
│   ├── scribe/         # ✍️ Technical writing
│   ├── forge/          # ⚒️ Feature implementation
│   ├── sheriff/        # 🤠 Test stability
│   ├── streamliner/    # 🌊 Data processing optimization
│   ├── weaver/         # 🕸️ Integration & builds
│   ├── simplifier/     # 📉 Complexity reduction
│   ├── organizer/      # 🗂️ Project organization
│   ├── taskmaster/     # 📋 Task identification
│   ├── essentialist/   # 💎 Pragmatic cuts
│   ├── sapper/         # 💣 Exception structuring
│   ├── maintainer/     # 🧭 Sprint planning & PM
│   └── pruner/         # 🪓 Dead code elimination
│
├── mail/               # Local mail storage (Maildir backend)
├── state/              # Local reconciliation state
│
├── sprints/            # Sprint planning and tracking
│   ├── current.txt     # Current sprint number
│   ├── sprint-1/       # Sprint 1 plans and feedback
│   ├── sprint-2/       # Sprint 2 plans and feedback
│   └── ...
│
├── schedules.toml      # Scheduler configuration
└── README.md           # This file
```

---

## 🤖 Personas

Each persona is an AI agent with a specific role and expertise. Personas work autonomously, creating PRs and maintaining journal entries of their work.

### Persona Structure

Each persona has:
- **`prompt.md`**: Persona definition with frontmatter
- **`journals/`**: Work logs (auto-created)

#### Persona Frontmatter

```yaml
---
id: curator              # Unique identifier
emoji: 🎭                # Visual identifier
description: "..."       # Role summary
---
```

**Note**: Operational settings (branch, title, automation_mode) are controlled by the scheduler, not persona configs.

### Active Personas

| Emoji | Name | Role | Focus |
| :---: | :--- | :--- | :--- |
| 🎭 | **Curator** | UX Designer | Blog evaluation, user experience |
| 🔧 | **Refactor** | Developer | Linting, TDD-based fixes |
| 🔮 | **Visionary** | Strategist | Moonshots, RFCs, innovation |
| ⚡ | **Bolt** | Perf. Engineer | Performance optimization |
| 🛡️ | **Sentinel** | Security | Vulnerability scanning |
| 🏗️ | **Builder** | Architect | Data architecture, schema design |
| 🧑‍🌾 | **Shepherd** | Test Engineer | Test coverage expansion |
| 🧹 | **Janitor** | Hygienist | Code cleanup, technical debt |
| 📚 | **Docs Curator** | Librarian | Documentation accuracy |
| 🔨 | **Artisan** | Craftsman | Code quality, refactoring |
| 🎨 | **Palette** | Design Sys | Accessibility, UI consistency |
| ✍️ | **Scribe** | Writer | Technical writing, content |
| ⚒️ | **Forge** | Builder | Feature implementation |
| 🤠 | **Sheriff** | Build Cop | Test stability, flake fixes |
| 🌊 | **Streamliner** | Optimizer | Data processing efficiency |
| 🕸️ | **Weaver** | Integrator | PR merging, integration builds |
| 📉 | **Simplifier** | Reducer | Complexity reduction |
| 🗂️ | **Organizer** | Maintainer | Project structure |
| 📋 | **Taskmaster** | Coordinator | Task identification |
| 💎 | **Essentialist** | Pragmatist | Strategic cuts, focus |
| 💣 | **Sapper** | Structurer | Exception handling patterns |
| 🧭 | **Maintainer** | PM | Sprint planning, coordination |
| 🪓 | **Pruner** | Eliminator | Dead code removal |

---

## ⚙️ Scheduler

The scheduler orchestrates persona execution in two modes: **Parallel Cycle** and **Scheduled**.

### Parallel Cycle Mode

Sequential execution per track, running multiple tracks in one tick:

```
curator → refactor → visionary → bolt → sentinel → ...
   ↓         ↓          ↓         ↓        ↓
  PR1  →   PR2   →    PR3   →   PR4  →   PR5
  merge    merge      merge     merge    merge
```

**How it works:**
1. Scheduler loads tracks from `schedules.toml` (or uses `cycle` as a default track).
2. Each track runs personas sequentially; a track waits for the previous session to finish.
3. Branching targets `jules` via `BranchManager`.
4. Persistent state lives in `.jules/cycle_state.json` (multi-track).
5. Reconciliation/merges are handled by `PRManager` after sessions complete.

**Benefits:**
- Sequential ensures no conflicts
- Each persona builds on previous work
- Sprint-based organization

### Scheduled Mode

Cron-based independent execution:

```toml
# schedules.toml
[schedules]
simplifier = "0 */2 * * *"    # Every 2 hours
organizer = "0 * * * *"        # Hourly
curator = "0 0 * * *"          # Daily at midnight
```

**How it works:**
1. Scheduler checks current time
2. Runs any persona matching its cron schedule
3. Creates PRs targeting `main`
4. Personas run independently (no inter-PR merging)

---

## 📅 Sprint System

Sprints organize work into cycles, providing context and continuity.

### Structure

```
.jules/sprints/
├── current.txt           # Current sprint number
├── sprint-1/
│   ├── curator-plan.md      # Curator's plan for sprint 1
│   ├── refactor-feedback.md # Refactor's feedback on plans
│   └── ...
├── sprint-2/
│   └── ...
```

### Sprint Flow

1. **Persona reads plans**: Each persona reads other personas' plans for upcoming sprints
2. **Persona provides feedback**: Creates `{persona}-feedback.md` files
3. **Persona creates plans**: Writes `{persona}-plan.md` for next 2 sprints
4. **Sprint increments**: When cycle completes, sprint number increments

### Sprint Context in Prompts

Every persona receives sprint context:
- Current sprint number
- Plans for next 2 sprints
- Feedback from other personas
- Templates for planning

---

## 🔧 Configuration

### schedules.toml

```toml
# Parallel cycle mode: Tracks run sequentially per track
[tracks]
default = ["personas/curator/prompt.md", "personas/refactor/prompt.md"]
ops = ["personas/sentinel/prompt.md.j2"]

# Scheduled mode: Cron schedules
[schedules]
simplifier = "0 */2 * * *"   # Every 2 hours
organizer = "0 * * * *"       # Hourly
curator = "0 0 * * *"         # Daily at midnight UTC
```

**Cron format:** `minute hour day month dayofweek`

### Environment Variables

```bash
# Required
export JULES_API_KEY="your-jules-api-key"

# Optional
export JULES_BASE_URL="https://jules.googleapis.com/v1alpha"
export GITHUB_TOKEN="your-github-token"
export GH_TOKEN="your-github-token"
export JULES_MAIL_STORAGE="local"  # or "s3"
export JULES_MAIL_BUCKET="jules-mail"
export AWS_S3_ENDPOINT_URL="https://s3.your-provider.example"
export JULES_PERSONA="weaver@team"
export PYTHONPATH=".jules"  # For running locally
```

---

## 🚀 Usage

### Running the Scheduler

```bash
# Parallel cycle mode (from CI or locally)
uv run jules schedule tick

# Run specific persona
uv run jules schedule tick --prompt-id curator

# Run all personas (ignore schedules)
uv run jules schedule tick --all

# Dry run (print without executing)
uv run jules schedule tick --dry-run
```

### Other CLI Commands

```bash
# Auto-fix PRs
uv run jules autofix analyze 1234

# Feedback loop
uv run jules feedback loop --dry-run

# Sync jules -> main directly (no PR)
uv run jules sync merge-main

# Mail CLI (local or S3 backend)
uv run mail inbox --persona curator@team
uv run mail send --to curator@team --subject "Status" --body "Done."

# Session + mail toolkit
uv run my-tools login --user weaver@team --password "<uuidv5>" --goals "Fix CI"
uv run my-tools email inbox --persona weaver@team
uv run my-tools journal --content "..." --password "<uuidv5>"
```

### CI Integration

The scheduler runs automatically via GitHub Actions:

- **Every 15 minutes**: Checks schedules and runs cycle tick
- **On CI success**: For `jules-sched-*` branches, triggers next cycle step

See `.github/workflows/jules_scheduler.yml`

---

## 📝 Persona Development

### Creating a New Persona

1. **Create directory:**
   ```bash
   mkdir -p .jules/personas/my_persona/journals
   ```

2. **Create `prompt.md.j2`:**
   ```jinja
   ---
   id: my_persona
   emoji: 🎯
   description: "You are My Persona - a specialist in X"
   ---

   {% extends "base/persona.md.j2" %}

   {% block content %}
   ## Your Mission

   [Detailed instructions...]
   {% endblock %}
   ```

3. **Add to cycle or schedule:**
   ```toml
   # schedules.toml
   [tracks]
   default = [
       # ... existing personas
       "personas/my_persona/prompt.md.j2",
   ]

   # OR
   [schedules]
   my_persona = "0 6 * * *"  # Daily at 6 AM UTC
   ```

### Persona Best Practices

1. **Be specific**: Clear, actionable instructions
2. **Use journals**: Reference past work to avoid duplication
3. **Coordinate**: Read other personas' plans
4. **Celebrate**: If nothing to do, say so (not a failure!)
5. **Document**: Update journals after each session

### Variable Injection

The scheduler injects these variables into prompts:

- `{{ id }}`: Persona identifier
- `{{ emoji }}`: The agent's brand emoji
- `{{ description }}`: Persona description from frontmatter
- `{{ journal_entries }}`: Aggregated content from `journals/*.md`
- `{{ password }}`: UUIDv5 derived from persona id (session auth)
- `{{ sprint_context_text }}`: Rendered sprint context

Templates can also include shared blocks and partials via:

- `base/persona.md.j2`
- `blocks/*.md.j2`
- `partials/*.md.j2`

---

## 🏗️ Architecture

### Scheduler Layout

The scheduler is organized by package:

```python
# Domain Models (.jules/jules/scheduler/models.py)
PersonaConfig    # Immutable persona data
CycleState       # Current cycle position (per track)
SessionRequest   # Session creation params
PRStatus         # PR status with CI checks

# Loading (.jules/jules/scheduler/loader.py)
PersonaLoader    # Load and parse personas

# State (.jules/jules/scheduler/state.py)
PersistentCycleState  # JSON-backed state + tracks

# Managers (.jules/jules/scheduler/managers.py)
BranchManager         # Git operations
PRManager             # GitHub PR operations
CycleStateManager     # Cycle progression logic
SessionOrchestrator   # Jules session creation

# Entry Points (.jules/jules/scheduler/engine.py)
execute_parallel_cycle_tick()  # Parallel cycle flow
execute_scheduled_tick()       # Scheduled mode flow
run_scheduler()                # CLI entry point
```

### Benefits

- **Clear separation of concerns**: Each class has one job
- **Type-safe**: Dataclasses ensure correctness
- **Testable**: Easy to mock and unit test
- **Readable**: Linear flow, no deep nesting
- **Maintainable**: Modify one part without breaking others

---

## 🧪 Testing

### Running Scheduler Tests

```bash
# Unit tests
uv run pytest tests/unit/jules/

# Integration tests
uv run pytest tests/skills/jules_api/

# Specific test
uv run pytest tests/unit/jules/test_scheduler.py
```

### Manual Testing

```bash
# Test persona loading
PYTHONPATH=.jules python -c "
from jules.scheduler.loader import PersonaLoader
from pathlib import Path
loader = PersonaLoader(Path('.jules/personas'), {})
personas = loader.load_personas(['personas/curator/prompt.md.j2'])
print(f'Loaded: {personas[0].id} {personas[0].emoji}')
"
```

---

## 🐛 Troubleshooting

### Scheduler Not Advancing

**Symptom**: Curator persona repeats, never advances to refactor

**Cause**: PRs not targeting correct base branch

**Fix**: Ensure personas don't override branch in frontmatter (fixed in recent commits)

### Session Stuck

**Symptom**: Session awaiting feedback/approval

**Solution**: Scheduler automatically approves plans and sends nudges

### Branch Conflicts

**Symptom**: Jules branch has conflicts with main

**Solution**: Scheduler automatically rotates drifted branch to `jules-sprint-N`

### Failed CI

**Symptom**: PR created but CI fails

**Solution**: Scheduler waits for green CI before merging. Fix failures in PR, or close and let scheduler continue.

---

## 📚 Additional Resources

- **Main README**: `/README.md` - Project overview
- **Code of the Weaver**: `/CLAUDE.md` - Contribution guidelines
- **Scheduler Diagnostic**: `/SCHEDULER_DIAGNOSTIC.md` - Debugging guide
- **Refactoring Plan**: `/SCHEDULER_REFACTORING_PLAN.md` - V2 design rationale

---

**Last Updated**: 2026-01-09
**Maintained By**: Weaver persona 🕸️ and human contributors
