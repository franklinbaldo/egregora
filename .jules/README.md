# Jules Automation System

This directory contains the Jules automation infrastructure for Egregora, including AI agent personas, scheduler configuration, and sprint planning.

## 📁 Directory Structure

```
.jules/
├── jules/              # Scheduler implementation
│   ├── scheduler.py    # Legacy scheduler (being phased out)
│   ├── scheduler_v2.py # Refactored scheduler (clean architecture)
│   ├── scheduler_models.py    # Domain models (PersonaConfig, CycleState, etc.)
│   ├── scheduler_loader.py    # Persona loading and prompt parsing
│   ├── scheduler_managers.py  # Manager classes (Branch, PR, Cycle, Session)
│   ├── client.py       # Jules API client
│   ├── github.py       # GitHub API helpers
│   ├── cli.py          # Command-line interface
│   └── exceptions.py   # Custom exceptions
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
├── blocks/             # Shared prompt blocks
│   ├── autonomy.md     # Autonomous decision-making guidelines
│   └── sprint_planning.md  # Sprint context and planning
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

The scheduler orchestrates persona execution in two modes: **Cycle** and **Scheduled**.

### Cycle Mode

Sequential execution with PR merging:

```
curator → refactor → visionary → bolt → sentinel → ...
   ↓         ↓          ↓         ↓        ↓
  PR1  →   PR2   →    PR3   →   PR4  →   PR5
  merge    merge      merge     merge    merge
```

**How it works:**
1. Scheduler starts first persona (curator)
2. Waits for PR to be created and pass CI
3. Merges PR into `jules` branch
4. Starts next persona (refactor)
5. Repeats until all personas complete
6. Increments sprint number and starts over

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
3. Creates PR targeting `main` branch
4. Personas run independently (no merging between them)

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
# Cycle mode: Sequential execution
cycle = [
    "personas/curator/prompt.md",
    "personas/refactor/prompt.md",
    # ... all personas in order
]

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
export GITHUB_TOKEN="your-github-token"

# Optional
export PYTHONPATH=".jules"  # For running locally
```

---

## 🚀 Usage

### Running the Scheduler

```bash
# Cycle mode (from CI or locally)
uv run --no-project --with requests --with python-frontmatter \
  --with jinja2 --with typer --with pydantic \
  python -m jules.cli schedule tick

# Run specific persona
uv run ... python -m jules.cli schedule tick --prompt-id curator

# Run all personas (ignore schedules)
uv run ... python -m jules.cli schedule tick --all

# Dry run (print without executing)
uv run ... python -m jules.cli schedule tick --dry-run
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

2. **Create `prompt.md`:**
   ```yaml
   ---
   id: my_persona
   emoji: 🎯
   description: "You are My Persona - a specialist in X"
   ---

   You are "My Persona" {{ emoji }} - [full role description]

   {{ identity_branding }}
   {{ pre_commit_instructions }}
   {{ autonomy_block }}
   {{ sprint_planning_block }}

   ## Your Mission

   [Detailed instructions...]
   ```

3. **Add to cycle or schedule:**
   ```toml
   # schedules.toml
   cycle = [
       # ... existing personas
       "personas/my_persona/prompt.md",
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

The scheduler automatically injects these variables into prompts:

- `{{ emoji }}`: The agent's brand emoji
- `{{ identity_branding }}`: Standard header with naming conventions
- `{{ pre_commit_instructions }}`: Required pre-commit instructions
- `{{ journal_management }}`: Standard instructions for writing journals
- `{{ empty_queue_celebration }}`: Standard logic for exiting when no work is found
- `{{ journal_entries }}`: Aggregated content from `journals/*.md`
- `{{ autonomy_block }}`: Autonomous decision-making guidelines
- `{{ sprint_planning_block }}`: Sprint context and planning

---

## 🏗️ Architecture

### Scheduler V2 (Refactored)

The scheduler has been refactored for clarity and testability:

```python
# Domain Models (scheduler_models.py)
PersonaConfig    # Immutable persona data
CycleState       # Current cycle position
SessionRequest   # Session creation params
PRStatus         # PR status with CI checks

# Loading (scheduler_loader.py)
PersonaLoader    # Load and parse personas

# Managers (scheduler_managers.py)
BranchManager         # Git operations
PRManager             # GitHub PR operations
CycleStateManager     # Cycle progression logic
SessionOrchestrator   # Jules session creation

# Entry Points (scheduler_v2.py)
execute_cycle_tick()      # Clean cycle mode flow
execute_scheduled_tick()  # Clean scheduled mode flow
```

### Benefits of V2

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
from jules.scheduler_loader import PersonaLoader
from pathlib import Path
loader = PersonaLoader(Path('.jules/personas'), {})
personas = loader.load_personas(['personas/curator/prompt.md'])
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
- **Architecture**: `/ARCHITECTURE_CLARIFICATION.md` - System design
- **Scheduler Diagnostic**: `/SCHEDULER_DIAGNOSTIC.md` - Debugging guide
- **Refactoring Plan**: `/SCHEDULER_REFACTORING_PLAN.md` - V2 design rationale

---

**Last Updated**: 2026-01-09
**Maintained By**: Weaver persona 🕸️ and human contributors
