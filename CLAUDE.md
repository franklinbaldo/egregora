# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Overview

**Egregora**: WhatsApp conversations → blog posts via LLM. Privacy-first staged pipeline with anonymization before AI processing.

- **Repository**: https://github.com/franklinbaldo/egregora
- **Python**: 3.12+ | **Package Manager**: uv | **Primary LLM**: Google Gemini

## Quick Commands

```bash
# Setup
uv sync --all-extras
python dev_tools/setup_hooks.py

# Test
uv run pytest tests/                    # All tests
uv run pytest tests/unit/               # Unit only
uv run pytest --cov=egregora tests/     # With coverage

# Lint
uv run pre-commit run --all-files       # All checks (line length: 110)
uv run ruff check --fix src/            # Auto-fix

# Run pipeline
export GOOGLE_API_KEY="your-key"
uv run egregora write export.zip --output=./output
uv run egregora write export.zip --step-size=100 --step-unit=messages

# Observability
uv run egregora runs tail               # Recent runs
uv run egregora runs show <run_id>      # Run details

# Serve
cd output && uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

**VCR cassettes**: First run needs `GOOGLE_API_KEY`, subsequent runs replay from `tests/cassettes/`.

## Parallel Subagent Delegation

For repetitive tasks across 5+ independent files:

**When to use**: Similar tasks, independent files, clear pattern, 5+ files
**How**: Launch multiple Task tool calls in single message

```python
# Example: Fix BLE001 across 10 files → 5 parallel subagents
Task 1: Fix BLE001 in writer_agent.py
Task 2: Fix BLE001 in cli.py
Task 3: Fix BLE001 in enrichment/batch.py + enrichment/core.py
```

**Subagent prompt guidelines**:
1. Exact file paths + error codes
2. Clear rules (e.g., "NEVER use `except Exception:`")
3. Verification command
4. Disable git operations
5. Request summary

**After completion**: Verify with `ruff check`, review diff, run tests, format, single commit

**Don't delegate**: Coordinated changes, interdependent files, exploratory work

## Post-Commit Reflection

After each commit/push, reflect on:
- Technical decisions and why
- What worked/didn't work
- Error patterns
- Architecture insights

Ask permission to update CLAUDE.md with valuable insights (non-obvious fixes, architecture decisions, design tradeoffs).

## Architecture: Staged Pipeline

```
Ingestion → Privacy → Augmentation → Knowledge ← Generation → Publication
Parse ZIP   UUIDs     LLM enrich      RAG/Elo     Writer      MkDocs
```

### Key Stages

1. **Ingestion** (`sources/whatsapp/`, `ingestion/`): `parse_source()` → `CONVERSATION_SCHEMA`
2. **Privacy** (`privacy/`): Names → UUIDs, PII detection BEFORE LLM
3. **Augmentation** (`enrichment/`): LLM URL/media descriptions, profiles
4. **Knowledge** (`agents/tools/`): RAG (DuckDB VSS), annotations, Elo rankings
5. **Generation** (`agents/writer/`): Pydantic-AI agent with tools (write_post, profiles, RAG)
6. **Publication** (`rendering/`): MkDocs + Jinja2 templates

### Design Principles

1. **Trust the LLM**: Full context → editorial decisions
2. **Ibis everywhere**: DuckDB tables, pandas only at boundaries
3. **Privacy-first**: Anonymize before LLM
4. **Schemas as contracts**: All stages preserve `CONVERSATION_SCHEMA`
5. **Functional transforms**: `Table → Table`
6. **Alpha mindset**: No backward compatibility, clean breaks

### Modern Patterns (Phases 2-7, 2025-01)

**Config objects**: `EgregoraConfig` + `RuntimeContext` dataclasses (no >5 params)
**Frozen dataclasses**: `@dataclass(frozen=True, slots=True)`
**Simple resume**: Check output exists → skip
**Source organization**: `sources/{whatsapp,slack}/`, generic in `ingestion/base.py`
**Generic naming**: `parse_source()` not `parse_export()`

**Flexible windowing (Phase 7)**:
- Units: `messages` (count), `hours`/`days` (time), `bytes` (text size)
- Sequential indices (0, 1, 2...) not calendar keys
- Runtime-only (NOT persisted)
- CLI: `--step-size`, `--step-unit`, `--min-window-size`

**View Registry (C.1)**:
- `ViewBuilder = Callable[[Table], Table]`
- Centralized pipeline transformations: `views.get("chunks")`
- Built-in: `chunks`, `hourly_aggregates`, `daily_aggregates`
- Register: `@views.register("my_view")`
- Docs: `docs/pipeline/view-registry.md`

**StorageManager (C.2)**:
- Centralized DuckDB + parquet checkpointing
- `with StorageManager() as storage:`
- `storage.write_table(table, "name", checkpoint=True)`
- `storage.execute_view("output", builder, "input")`
- Docs: `docs/database/storage-manager.md`

**Stage Validation (C.3)**:
- `@validate_stage` decorator for IR schema validation
- Two-level: compile-time + runtime
- Docs: `docs/pipeline/stage-validation.md`

**Run Tracking (D.1)**:
- Auto tracking in `.egregora/runs.duckdb`
- `egregora runs tail` / `egregora runs show <run_id>`
- Observability only (don't depend on for pipeline logic)
- Docs: `docs/observability/runs-tracking.md`

**OpenTelemetry (D.2)**:
- Opt-in: `EGREGORA_OTEL=1`
- Exporters: Logfire → OTLP → Console
- No mandatory keys
- Functions: `get_tracer()`, `get_current_trace_id()`

**Agent Skill Injection (2025-01-11)**:
- Sub-agents via `use_skill(ctx, "skill-name", "task")`
- Skills in `.egregora/skills/*.md`
- Parent gets summary only
- Deps must implement `SkillInjectionSupport` protocol
- Files: `agents/tools/skill_loader.py`, `skill_injection.py`
- Tests: `tests/agents/test_skill_injection.py`
- Docs: `.egregora/skills/README.md`

## Code Structure

```
src/egregora/
├── cli.py                    # Entry point
├── pipeline.py               # Windowing
├── database/
│   ├── schema.py            # All schemas
│   ├── storage.py           # StorageManager (C.2)
│   └── validation.py        # IR validation
├── config/                   # Config dataclasses
├── pipeline/
│   ├── views.py             # View registry (C.1)
│   ├── tracking.py          # Run tracking (D.1)
│   └── checkpoint.py        # Content-addressed checkpointing
├── ingestion/base.py         # Generic interfaces
├── sources/whatsapp/         # WhatsApp-specific
├── privacy/                  # Anonymization, PII
├── enrichment/               # LLM enrichment
├── agents/
│   ├── writer/              # Main agent
│   ├── editor/              # Post refinement
│   ├── ranking/             # Elo
│   └── tools/               # RAG, annotations, profiler, skills
├── utils/
│   ├── telemetry.py         # OpenTelemetry (D.2)
│   └── cache.py             # DiskCache
└── rendering/               # MkDocs + templates
```

## Database Schemas

All in `database/schema.py`:

**Ephemeral** (in-memory):
- `CONVERSATION_SCHEMA`: Pipeline data (timestamp, author, message, etc.)

**Persistent** (DuckDB/Parquet):
- `RAG_CHUNKS_SCHEMA`: Vector embeddings
- `ANNOTATIONS_SCHEMA`: Conversation metadata
- `ELO_RATINGS_SCHEMA`: Post quality

**Invariant**: All stages preserve `CONVERSATION_SCHEMA`

## Testing

- `tests/unit/`: Pure functions
- `tests/integration/`: DuckDB, API (VCR)
- `tests/e2e/`: Full pipeline (golden fixtures)
- `tests/agents/`: Agent tests

**VCR**: Record/replay Gemini calls (cassettes in `tests/cassettes/`)
**Golden fixtures**: `tests/fixtures/golden/expected_output/`
**VSS**: Use `--retrieval-mode=exact` in CI

## Configuration

**Env vars**: Only `GOOGLE_API_KEY`

**Config file**: `.egregora/config.yml` (maps to `EgregoraConfig`)

```yaml
models:
  writer: google-gla:gemini-2.0-flash-exp
  enricher: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001

rag:
  enabled: true
  top_k: 5
  mode: ann                    # "ann" or "exact"

writer:
  custom_instructions: "..."
  enable_banners: true

pipeline:
  step_size: 100
  step_unit: messages          # "messages", "hours", "days", "bytes"
```

**Custom prompts**: `.egregora/prompts/` overrides `src/egregora/prompts/`

### Model Thinking/Reasoning

Enable thinking for complex tasks:

```python
# Gemini
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
settings = GoogleModelSettings(google_thinking_config={'include_thoughts': True})

# Claude
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
settings = AnthropicModelSettings(anthropic_thinking={'type': 'enabled', 'budget_tokens': 1024})
```

**Token tracking**: `tokens_input`, `tokens_output`, `tokens_cache_*`, `tokens_thinking`, `tokens_reasoning`

**Journal entries**: Auto-saved to `output/journal/journal_*.md`
- Intercalated log: thinking + freeform + tool calls/returns
- YAML frontmatter with timestamp
- Benefits: transparency, debugging, audit trail, continuity

## Development Workflow

### Adding Features

1. Identify pipeline stage
2. Check if `CONVERSATION_SCHEMA` needs updates (rarely)
3. Write tests first
4. Keep simple (can LLM do it with better prompting?)
5. Update docs

### Modifying Stages

- All stages: `Table → Table`
- Privacy MUST run before LLM
- Preserve `CONVERSATION_SCHEMA` columns
- Add columns via `.mutate()`, never drop core

### Adding Agent Tools

1. Define in `agents/writer/tools.py`
2. Register in `ToolRegistry`
3. Add to agent init
4. Test with VCR

### Debugging

```python
# Inspect Ibis tables
table.schema()
table.limit(5).execute()

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check VSS extension
conn.execute("SELECT * FROM duckdb_extensions() WHERE extension_name = 'vss'")
```

## TENET-BREAK Philosophy

Intentional principle violations:

**Tenets**: `no-compat`, `clean`, `no-defensive`, `propagate-errors`

**Format**:
```python
# TENET-BREAK(scope)[@owner][P0|P1|P2][due:YYYY-MM-DD]:
# tenet=<code>; why=<constraint>; exit=<condition> (#issue)
```

See `CONTRIBUTING.md` for details.

## Privacy & Security

**Flow**: Parse → UUIDs (deterministic) → PII scan → LLM (anonymized only)

**In-chat commands**:
```
/egregora set alias "Casey"
/egregora opt-out
/egregora opt-in
```

## Common Pitfalls

1. Never bypass privacy stage
2. Use Ibis, not pandas (convert only at boundaries)
3. Respect schemas in `database/schema.py`
4. Commit VCR cassettes to repo
5. Use `--retrieval-mode=exact` without VSS extension

## Dependencies

**Core**: Ibis, DuckDB, Pydantic-AI, Google Gemini, MkDocs Material, uv
**Optional**: pytest-vcr, Pydantic Logfire, mkdocs-rss-plugin

## Deployment

```bash
cd output && mkdocs build
mkdocs gh-deploy
# Or: Netlify/Vercel/Cloudflare Pages (deploy ./site/)
```

## Related Docs

- `README.md`: User docs, quick start
- `CONTRIBUTING.md`: TENET-BREAK philosophy
- `docs/`: Architecture, privacy, API reference
- `tests/fixtures/golden/`: Example outputs
