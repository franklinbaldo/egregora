# Persona System

> How Egregora uses AI personas to maintain and improve the codebase.

## Overview

Egregora uses a sophisticated **persona system** to enable autonomous AI agents (powered by Google's Jules) to collaborate on development tasks. Each persona is a specialized agent with a specific role, expertise, and workflow.

## Architecture

### Template System

Personas are defined using **Jinja2 templates** with inheritance, allowing for consistent structure while enabling customization.

```
.team/
├── personas/           # Individual persona definitions
│   ├── curator/
│   │   ├── prompt.md.j2    # Persona template
│   │   └── journals/       # Session history
│   ├── forge/
│   ├── lore/
│   └── ...
└── repo/
    └── templates/
        ├── base/
        │   └── persona.md.j2    # Base template (RGCCOV framework)
        ├── blocks/              # Reusable prompt sections
        └── partials/            # Smaller template components
```

### RGCCOV Framework

All personas follow the **RGCCOV** framework, which structures prompts into:

- **R**ole: Who you are, your expertise
- **G**oal: Specific objective to achieve
- **C**ontext: Background, references, current state
- **C**onstraints: Rules, limitations, boundaries
- **O**utput: Expected deliverables format
- **V**erification: How to confirm success

This framework is implemented in `.team/repo/templates/base/persona.md.j2`.

### Prompt Rendering

Personas are rendered using the `PersonaLoader` class:

```python
from pathlib import Path
from repo.scheduler.loader import PersonaLoader

# Initialize loader
loader = PersonaLoader(
    personas_dir=Path('.team/personas'),
    base_context={}
)

# Load specific persona
personas = loader.load_personas(['personas/curator/prompt.md.j2'])
curator = personas[0]

# Access rendered prompt
print(curator.prompt_body)
```

### Context Variables

The rendering system automatically injects these variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `id` | Persona identifier | `"curator"` |
| `emoji` | Persona emoji | `"🎭"` |
| `description` | Brief role description | `"UX/UI designer"` |
| `journal_entries` | Last 10 journal entries | Recent session notes |
| `password` | Session UUID | `"6b67ff37-a96b..."` |
| `sprint_context_text` | Current sprint info | Sprint goals, tasks |

## Creating a New Persona

### Step 1: Choose a Role

Identify a specific responsibility or expertise area not covered by existing personas.

**Good examples:**
- ✅ Security auditor specializing in OWASP vulnerabilities
- ✅ Performance optimizer for database queries
- ✅ Documentation curator for API references

**Bad examples:**
- ❌ Generic "developer" (too broad)
- ❌ "Helper agent" (no clear expertise)

### Step 2: Create Directory Structure

```bash
mkdir -p .team/personas/your-persona/journals
touch .team/personas/your-persona/prompt.md.j2
```

### Step 3: Define the Template

Create `.team/personas/your-persona/prompt.md.j2`:

{% raw %}
```jinja
{% raw %}
---
description: One-line description of your persona
emoji: 🔧
id: your-persona
hired_by: franklin  # Who created this persona
pronouns: they/them
---

{% extends "base/persona.md.j2" %}

{% block role %}
Detailed description of your role and expertise.
{% endblock %}

{% block goal %}
Specific objective this persona achieves.
{% endblock %}

{% block context %}
**Reference Documents:**
- Link to relevant docs
- Background information

**Key Locations:**
- `src/path/to/relevant/code/`
{% endblock %}

{% block constraints %}
- Specific rules for this persona
- Limitations or boundaries
{% endblock %}

{% block guardrails %}
**✅ Always:**
- Do this thing
- Follow this pattern

**🚫 Never:**
- Avoid this
- Don't do that
{% endblock %}

{% block verification %}
- How to verify task completion
- Success criteria
{% endblock %}

{% block workflow %}
### Daily Process

1. **STEP 1**: What to do first
2. **STEP 2**: Next action
3. **STEP 3**: Final verification
{% endblock %}
{% endraw %}
```
{% endraw %}

### Step 4: Test Rendering

```bash
PYTHONPATH=.team uv run python -c "
from pathlib import Path
from repo.scheduler.loader import PersonaLoader

loader = PersonaLoader(personas_dir=Path('.team/personas'))
personas = loader.load_personas(['personas/your-persona/prompt.md.j2'])
print(personas[0].prompt_body)
"
```

### Step 5: Register Persona

New personas are automatically discovered by the `PersonaLoader` by scanning the `.team/personas/` directory. No central roster file is required.

## Available Blocks and Partials

### Standard Blocks (Auto-Included)

These are automatically included from the base template:

- `identity` - Branding and emoji usage
- `environment` - Jules session context
- `session_protocol` - Login, journal, PR workflow
- `communication` - Email, tasks, ADR, wiki
- `voting` - Democratic process for scheduling
- `skills` - Access to specialized skill modules
- `governance` - Team constitution
- `autonomy` - Independence guidelines
- `journal` - Journal management
- `pre_commit` - Pre-commit hook instructions

You can override any of these by redefining the block in your persona template.

### Common Partials

Reference these in your custom blocks:

{% raw %}
```jinja
{% raw %}
{% include "blocks/bdd_technique.md.j2" %}  # BDD testing guidance
{% include "blocks/pr_format.md.j2" %}      # Standardized PR template
{% include "partials/celebration.md.j2" %}  # Empty queue celebration
{% endraw %}
```
{% endraw %}

## Persona Communication

### Email System

Personas communicate via `.team/mail/`. Run commands using the `my-tools` CLI wrapper:

```bash
# Send message
PYTHONPATH=.team uv run python .team/repo/cli/my_tools.py email send --to curator --subject "Question" --body "..."

# Check inbox
PYTHONPATH=.team uv run python .team/repo/cli/my_tools.py email inbox

# Broadcast to all
PYTHONPATH=.team uv run python .team/repo/cli/my_tools.py email send --to all@team --subject "Announcement" --body "..."
```

### Task Management

Shared task queue at `.team/tasks/`:

```bash
.team/tasks/
├── todo/          # Pending tasks
├── in_progress/   # Active work
└── done/          # Completed
```

Tasks use TOML format with BDD acceptance criteria.

### Journal Entries

Each persona maintains session notes:

```bash
PYTHONPATH=.team uv run python .team/repo/cli/my_tools.py journal --content "Session summary" --password <uuid>
```

Journals are automatically included in future prompts (last 10 entries).

## Best Practices

### 1. Single Responsibility

Each persona should have **one clear purpose**. Don't create "jack-of-all-trades" personas.

✅ Good: `curator` - UX/UI evaluation only
❌ Bad: `developer` - does everything

### 2. Autonomous Operation

Personas must work **independently** without human input:

{% raw %}
```jinja
{% raw %}
{% block constraints %}
- Make decisions autonomously
- Don't ask humans for approval
- Document uncertainties in journal
{% endblock %}
{% endraw %}
```
{% endraw %}

### 3. Clear Verification

Always define **measurable success criteria**:

{% raw %}
```jinja
{% raw %}
{% block verification %}
- All tests pass (run `uv run pytest`)
- Linter shows 0 errors (run `uv run ruff check`)
- Documentation updated in docs/
{% endblock %}
{% endraw %}
```
{% endraw %}

### 4. Precise Context

Provide **exact file paths** and references:

✅ Good: `src/egregora/agents/writer.py:45-67`
❌ Bad: "somewhere in the agents folder"

### 5. Emoji Consistency

Use the persona's emoji in all outputs:

```jinja
**PR Title:** 🎭 curator: Update UX vision
**Journal:** ## 🎭 2026-01-22 - Session Summary
**Commits:** 🎭 docs: improve accessibility
```

## Advanced Features

### Sprint Planning Integration

Personas receive sprint context automatically:

```python
from repo.features.sprints import sprint_manager

sprint_context = sprint_manager.get_sprint_context("curator")
# Injects current sprint goals into prompt
```

### Conditional Rendering

Use Jinja2 conditionals for flexible prompts:

{% raw %}
```jinja
{% raw %}
{% if journal_entries %}
## Previous Work
{{ journal_entries }}
{% else %}
This is your first session!
{% endif %}
{% endraw %}
```
{% endraw %}

### Custom Password Generation

Each persona gets a unique UUID-based password:

```python
import uuid
password = str(uuid.uuid5(uuid.NAMESPACE_DNS, persona_id))
```

## Troubleshooting

### Template Won't Render

**Error:** `TemplateNotFound: base/persona.md.j2`

**Fix:** Ensure `PYTHONPATH=.team` is set:
```bash
PYTHONPATH=.team uv run python ...
```

### Missing Context Variables

**Error:** `UndefinedError: 'journal_entries' is undefined`

**Fix:** Use the PersonaLoader, don't render templates directly:
```python
# ❌ Wrong
env.get_template('personas/curator/prompt.md.j2').render()

# ✅ Correct
loader = PersonaLoader(...)
loader.load_personas(['personas/curator/prompt.md.j2'])
```

### Journal Not Appearing

**Issue:** Journal entries not showing in prompt

**Fix:** Ensure journals are in correct location:
```
.team/personas/your-persona/journals/YYYY-MM-DD-HHMM-Title.md
```

## Reference

### Key Files

- `.team/repo/scheduler/loader.py` - PersonaLoader implementation
- `.team/repo/scheduler/models.py` - PersonaConfig dataclass
- `.team/repo/templates/base/persona.md.j2` - Base template
- `.team/repo/cli/my_tools.py` - CLI for persona operations

### Persona Roster

The team consists of specialized agents:

<<<<<<< HEAD
- **curator** - UX/UI evaluation with BDD
- **forge** - Code implementation
- **lore** - Knowledge base management
- **oracle** - System coordination
=======
- **absolutist** 💯 - Code cleanup & legacy removal
- **artisan** 🔨 - Code craftsmanship & refactoring
- **bolt** ⚡ - Performance & latency optimization
- **curator** 🎭 - UX/UI evaluation & content strategy
- **forge** ⚒️ - Implementation & frontend polish
- **lore** 📚 - History, documentation & knowledge base
- **maya** 💝 - User advocacy & family perspective
- **meta** 🔍 - System introspection & validation
- **refactor** 🧹 - Technical debt reduction
- **sapper** 💣 - Resilience, error handling & edge cases
- **scribe** ✍️ - Documentation & user guides
- **sentinel** 🛡️ - Security & compliance
- **simplifier** 📉 - Architecture reduction & complexity management
- **steward** 🧠 - Strategic alignment & decisions
- **streamliner** 🌊 - Data pipeline optimization
- **visionary** 🔭 - Future features & innovation
>>>>>>> origin/pr/2867

### Related Documentation

<<<<<<< HEAD
<<<<<<< HEAD
- [Team Constitution](https://github.com/franklinbaldo/egregora/blob/main/.team/CONSTITUTION.md)
- [Parallel Personas](https://github.com/franklinbaldo/egregora/blob/main/.team/PARALLEL_PERSONAS_README.md)
- [Code of the Weaver](https://github.com/franklinbaldo/egregora/blob/main/CLAUDE.md)
=======
- [Team Constitution]({{ config.repo_url }}/blob/main/.team/CONSTITUTION.md)
- [Parallel Personas]({{ config.repo_url }}/blob/main/.team/PARALLEL_PERSONAS_README.md)
- [Code of the Weaver]({{ config.repo_url }}/blob/main/CLAUDE.md)
>>>>>>> origin/pr/2872
=======
- [Team Constitution](https://github.com/franklinbaldo/egregora/blob/main/.team/CONSTITUTION.md)
- [Parallel Personas](https://github.com/franklinbaldo/egregora/blob/main/.team/PARALLEL_PERSONAS_README.md)
- [Code of the Weaver](https://github.com/franklinbaldo/egregora/blob/main/CLAUDE.md)
>>>>>>> origin/pr/2860

---

*This documentation is maintained by the team. Last updated: 2026-01-22*
