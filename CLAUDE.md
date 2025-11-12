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

## Naming Conventions (Updated 2025-01)

Egregora follows PEP 8 and Python idioms for clear, consistent naming across the codebase.

### Module Names

- **Use descriptive snake_case**: `file_system.py` not `filesystem.py`
- **Be specific over generic**: `duckdb_manager.py` not `storage.py`, `writer_runner.py` not `core.py`
- **Avoid redundant names**: `llm_tools.py` not `shared/shared.py`

### Class Names

**Configuration (Pydantic models in `config/settings.py`)**:
- Pattern: `*Settings` for Pydantic BaseModel configs
- Examples: `ModelSettings`, `RAGSettings`, `PipelineSettings`, `WriterAgentSettings`
- Distinguishes Pydantic models (persisted) from runtime dataclasses (ephemeral)

**Runtime contexts (dataclasses)**:
- Pattern: `*Context` or `*Config` for runtime-only dataclasses
- Examples: `WriterAgentContext`, `ProcessConfig`, `RuntimeContext`
- Never persisted, used for function parameters

**Database**:
- Pattern: `{Technology}{Purpose}` for managers
- Examples: `DuckDBStorageManager` not `StorageManager`
- Pattern: `{Domain}{Type}` for data models
- Examples: `IRMessageRow` not `IRv1Row`, `IR_MESSAGE_SCHEMA` not `IR_V1_SCHEMA`

**Utils**:
- Pattern: `*Settings` for configuration dataclasses
- Example: `ZipValidationSettings` not `ZipValidationLimits`

**Adapters (System Boundaries)**:
- Pattern: `Input*` for bringing data INTO the pipeline, `Output*` for taking data OUT
- Examples: `InputAdapter` not `SourceAdapter`, `OutputAdapter` not `OutputFormat`
- Registries: `InputAdapterRegistry`, `OutputAdapterRegistry`
- Implementations: `WhatsAppAdapter`, `SlackAdapter` (implement `InputAdapter`)
- Implementations: `MkDocsOutputAdapter`, `HugoOutputAdapter` (implement `OutputAdapter`)
- Rationale: Creates clear symmetry defining system boundaries (IN vs OUT)

### Function Names

- **Use explicit verbs**: `get_adapter_metadata()` not `adapter_meta()`
- **Be descriptive**: `embed_texts_in_batch()` not `embed_batch()`
- **Clarify purpose**: `embed_query_text()` not `embed_query()`

### Variable Names

- **Source-agnostic naming**: `input_file` not `zip_file`, `input_path` not `zip_path`
- **Explicit thresholds**: `min_similarity_threshold` not `min_similarity`

### File Renames Summary

| Old                                | New                                    | Rationale                          |
|------------------------------------|----------------------------------------|------------------------------------|
| `config/schema.py`                 | `config/settings.py`                   | Settings not schema                |
| `database/storage.py`              | `database/duckdb_manager.py`           | Explicit technology                |
| `database/schemas.py`              | `database/ir_schema.py`                | Focus on IR                        |
| `utils/filesystem.py`              | `utils/file_system.py`                 | PEP 8 snake_case                   |
| `utils/dates.py`                   | `utils/time_utils.py`                  | Broader scope                      |
| `agents/shared/shared.py`          | `agents/shared/llm_tools.py`           | Avoid redundancy                   |
| `agents/shared/profiler.py`        | `agents/shared/author_profiles.py`     | Noun-based clarity                 |
| `agents/writer/core.py`            | `agents/writer/writer_runner.py`       | Explicit role                      |
| `agents/writer/context.py`         | `agents/writer/context_builder.py`     | Action-based naming                |
| `agents/banner/generator.py`       | `agents/banner/image_generator.py`     | Content type explicit              |
| `storage/output_format.py`         | `storage/output_adapter.py`            | Adapter not just format            |
| `rendering/mkdocs_output_format.py` | `output_adapters/mkdocs_output_adapter.py` | Consistent adapter naming   |

### Package Renames Summary

| Old                | New                      | Rationale                                    |
|--------------------|--------------------------|----------------------------------------------|
| `core/` + `types.py` | `data_primitives/`     | Consolidates fundamental data models         |
| `adapters/`        | `input_adapters/`        | Explicit: brings data INTO pipeline          |
| `rendering/`       | `output_adapters/`       | Explicit: takes data OUT of pipeline         |

## Architecture: Staged Pipeline

```
Ingestion → Privacy → Augmentation → Knowledge ← Generation → Publication
Parse ZIP   UUIDs     LLM enrich      RAG/Elo     Writer      MkDocs
```

These stages are coordinated by the **orchestration layer** (`orchestration/`), which provides high-level workflows like `write_pipeline.run()` that execute the complete sequence.

### Key Stages

1. **Ingestion** (`sources/`, `input_adapters/`): `InputAdapter` → `parse()` → `CONVERSATION_SCHEMA`
2. **Privacy** (`privacy/`): Names → UUIDs, PII detection BEFORE LLM
3. **Augmentation** (`enrichment/`): LLM URL/media descriptions, profiles
4. **Knowledge** (`agents/tools/`): RAG (DuckDB VSS), annotations, Elo rankings
5. **Generation** (`agents/writer/`): Pydantic-AI agent with tools (write_post, profiles, RAG)
6. **Publication** (`output_adapters/`): `OutputAdapter` → `serve()` → MkDocs/Hugo/etc.

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

**DuckDBStorageManager (C.2)**:
- Centralized DuckDB + parquet checkpointing
- `with DuckDBStorageManager() as storage:`
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

**Three-Layer Architecture**: The codebase follows clean architecture with explicit separation:

**Layer 3: Business Workflows** (`orchestration/`)
- High-level execution flows for user-facing commands
- Coordinates stages to accomplish specific goals
- `write_pipeline.py`: Complete write workflow (ingest → process → generate → publish)

**Layer 2: Infrastructure** (`pipeline/`, `input_adapters/`, `output_adapters/`)
- Generic, reusable mechanisms for data processing
- `pipeline/`: Windowing, tracking, views, validation
- `input_adapters/`: Brings external data IN
- `output_adapters/`: Takes structured data OUT

**Layer 1: Foundation** (`data_primitives/`, `database/`)
- Core data models and persistence
- `data_primitives/`: Document, GroupSlug, PostSlug
- `database/`: DuckDB management, IR schemas

```
src/egregora/
├── cli.py                    # Entry point → delegates to orchestration/
├── orchestration/            # HIGH-LEVEL WORKFLOWS
│   ├── write_pipeline.py    # Write command orchestration (WHAT to execute)
│   ├── read_pipeline.py     # (Future) Read agent workflow
│   └── edit_pipeline.py     # (Future) Edit agent workflow
├── data_primitives/          # CORE DATA MODELS
│   ├── document.py          # Document, DocumentType, DocumentCollection
│   └── base_types.py        # GroupSlug, PostSlug
├── database/
│   ├── ir_schema.py         # All schemas (renamed from schemas.py)
│   ├── duckdb_manager.py    # DuckDBStorageManager (C.2) (renamed from storage.py)
│   └── validation.py        # IR validation
├── config/
│   ├── settings.py          # Pydantic settings models (renamed from schema.py)
│   └── ...                  # Other config files
├── pipeline/
│   ├── views.py             # View registry (C.1)
│   ├── tracking.py          # Run tracking (D.1)
│   └── checkpoint.py        # Content-addressed checkpointing
├── sources/                  # InputAdapter base class
├── input_adapters/           # Concrete input adapters (renamed from adapters/)
│   ├── whatsapp.py          # WhatsAppAdapter
│   └── slack.py             # SlackAdapter
├── privacy/                  # Anonymization, PII
├── enrichment/               # LLM enrichment
├── agents/
│   ├── writer/
│   │   ├── writer_runner.py # Main orchestration (renamed from core.py)
│   │   ├── context_builder.py # Prompt context (renamed from context.py)
│   │   └── agent.py         # Writer agent
│   ├── banner/
│   │   └── image_generator.py # Banner generation (renamed from generator.py)
│   ├── shared/
│   │   ├── llm_tools.py     # LLM tool functions (renamed from shared.py)
│   │   ├── author_profiles.py # Author profiling (renamed from profiler.py)
│   │   └── rag/             # RAG implementation
│   ├── editor/              # Post refinement
│   ├── ranking/             # Elo
│   └── tools/               # Skills and tool injection
├── output_adapters/          # Concrete output adapters (renamed from rendering/)
│   ├── base.py              # OutputAdapter protocol
│   ├── mkdocs_output_adapter.py  # MkDocs implementation
│   └── mkdocs_site.py       # MkDocs site structure
├── storage/                  # Output adapter utilities
│   └── output_adapter.py    # OutputAdapter base implementations
└── utils/
    ├── telemetry.py         # OpenTelemetry (D.2)
    ├── file_system.py       # File utilities (renamed from filesystem.py)
    ├── time_utils.py        # Date/time utilities (renamed from dates.py)
    └── cache.py             # DiskCache
```

## Database Schemas

All in `database/ir_schema.py`:

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

## Slug Collision Behavior (OutputFormat)

**P1 Badge Response**: The `serve()` method has **intentional overwriting behavior** for slug-based paths.

### Design Rationale

**Posts** (slug + date):
- Path: `posts/YYYY-MM-DD-{slug}.md`
- Collision: **Overwrites** (second post with same slug+date replaces first)
- Rationale: Posts are identified by (slug, date), not content. Writing the same slug twice should UPDATE the file, like `UPDATE` in SQL or `PUT` in REST. This is idempotent publishing.

**Profiles** (UUID):
- Path: `profiles/{uuid}.md`
- Collision: **Overwrites** (updating profile for same UUID)
- Rationale: Profiles are identified by UUID. Updating a user's profile should replace the existing file, not create duplicates.

**Enrichment URLs** (content hash):
- Path: `enrichments/{hash}.md`
- Collision: **Detects and resolves** with suffix (`{hash}-1.md`)
- Rationale: Hash collisions are rare but theoretically possible. Resolution adds numeric suffix.

### Error Reporting (Future Enhancement)

Currently `serve()` returns `None` (fire-and-forget). If collision reporting is needed:

**Option 1**: Add optional return type (backward compatible)
```python
def serve(self, document: Document) -> ServeResult | None:
    """Returns ServeResult if error, None if success."""
```

**Option 2**: Use exceptions for errors
```python
def serve(self, document: Document) -> None:
    """Raises ServeError on collision (if strict mode enabled)."""
    if strict and path.exists():
        raise SlugCollisionError(...)
```

**Decision**: DEFER until needed. Current overwriting behavior is correct for idempotent publishing.

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
