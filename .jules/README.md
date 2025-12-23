# Jules Agents

This directory contains the definitions and memory for the autonomous agents (personas) operating on this repository.

## Structure

```
.jules/
├── schedules.toml          # Central schedule registry
├── personas/               # Agent definitions
│   ├── <agent_name>/
│   │   ├── prompt.md       # Persona definition (Jinja2 + Frontmatter)
│   │   └── journals/       # Append-only memory of past actions
```

## Active Personas

| Emoji | Name | Role | Focus |
| :---: | :--- | :--- | :--- |
| 🔮 | **Visionary** | Strategist | Moonshots, RFCs, Innovation |
| 🎭 | **Curator** | UX Designer | User Experience, Blog Evaluation |
| 🧹 | **Janitor** | Hygienist | Code Cleanup, Technical Debt |
| 🔨 | **Artisan** | Craftsman | Code Quality, Refactoring |
| ⚒️ | **Forge** | Builder | Feature Implementation (MkDocs) |
| 📚 | **Docs Curator**| Librarian | Documentation Accuracy |
| ✍️ | **Scribe** | Writer | Content & Guides |
| 🧑‍🌾 | **Shepherd** | Test Engineer | Coverage & Behavior |
| 🤠 | **Sheriff** | Build Cop | Test Stability & Flakes |
| 🔧 | **Refactor** | Developer | Linting & TDD |
| 🪓 | **Pruner** | Eliminator | Dead Code Removal |
| 🕸️ | **Weaver** | Integrator | PR Merging & Builds |
| ⚡ | **Bolt** | Perf. Engineer | Optimization |
| 🏗️ | **Builder** | Architect | Data & Schema |
| 🎨 | **Palette** | Design Sys | Accessibility & UI |
| 🛡️ | **Sentinel** | Security | Vulnerabilities |

## Configuration

Each `prompt.md` supports the following Frontmatter:

```yaml
---
id: agent_id
emoji: 🤖
enabled: true
title: "{{ emoji }} task: description"
---
```

## Variable Injection

The scheduler automatically injects standard variables into the prompt context:

- `{{ emoji }}`: The agent's brand emoji.
- `{{ identity_branding }}`: Standard header with naming conventions.
- `{{ journal_management }}`: Standard instructions for writing journals.
- `{{ empty_queue_celebration }}`: Standard logic for exiting when no work is found.
- `{{ journal_entries }}`: Aggregated content from `journals/*.md`.