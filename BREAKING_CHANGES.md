# Breaking Changes: Phases 2-6 Modernization (2025-01)

This document tracks breaking changes introduced during the comprehensive modernization effort (Phases 2-6).

**Philosophy**: Alpha development - no backward compatibility. Clean breaks for better architecture.

---

## Phase 2: Configuration Objects (Pydantic V2)

### Function Signature Changes

**writer_agent.py**:
- ❌ OLD: `write_posts_with_pydantic_agent(...12 parameters...)`
- ✅ NEW: `write_posts_with_pydantic_agent(prompt, config, context, test_model=None)`
- **Migration**: Bundle parameters into `EgregoraConfig` and `WriterRuntimeContext`

**enrichment/core.py**:
- ❌ OLD: `enrich_table(...13 parameters...)`
- ✅ NEW: `enrich_table(messages_table, media_mapping, config, context)`
- **Migration**: Use `EgregoraConfig` and `EnrichmentRuntimeContext`

**pipeline/runner.py**:
- ❌ OLD: `run_source_pipeline(...16 parameters...)`
- ✅ NEW: `run_source_pipeline(source, input_path, output_dir, config, api_key, model_override=None, client=None)`
- **Migration**: Pass `EgregoraConfig` instead of individual config values

### Configuration Schema Changes

**config/types.py**:
- ❌ REMOVED: `ProcessConfig.resume` field
- **Migration**: Resume logic now automatic (checks for existing output files)

**config/schema.py**:
- ❌ REMOVED: `PipelineConfig.resume` field
- **Migration**: No configuration needed - pipeline auto-detects existing work

---

## Phase 3: Pipeline Decomposition

### Checkpoint System Removal

**BREAKING CHANGE**: Complex checkpoint system with JSON metadata completely removed.

**Before** (Phase 2):
```python
checkpoint_store = CheckpointStore(site_root / ".egregora" / "checkpoints")
checkpoint_store.update_step(period_key, "enrichment", "in_progress")
# ... complex checkpoint tracking ...
```

**After** (Phase 3):
```python
# Simple file existence check
existing_posts = sorted(posts_dir.glob(f"{period_key}-*.md"))
if existing_posts:
    continue  # Skip this period
```

**Migration**:
- Delete `.egregora/checkpoints/` directory (no longer used)
- Delete `.egregora/enriched/` directory (no longer caching CSVs)
- Resume logic is automatic - just re-run the pipeline

### API Changes

**pipeline/runner.py**:
- ❌ REMOVED: `resume` parameter (now automatic)
- ❌ REMOVED: `_load_enriched_table()` helper function
- ❌ REMOVED: Enriched CSV caching to `.egregora/enriched/`
- ✅ NEW: Simple skip logic checks `posts/*.md` for existing work

---

## Phase 4: CLI Command Decomposition

### CLI Flag Changes

**egregora process** command:
- ❌ REMOVED: `--resume` flag (behavior is now automatic)
- ✅ BEHAVIOR: Pipeline auto-detects existing posts and skips those periods

**egregora enrich** command:
- ✅ UPDATED: Now uses Phase 2 signature (4 parameters instead of 11)
- **Migration**: No user-facing changes, but internal implementation modernized

---

## Phase 5: Parser Modernization

**Status**: pyparsing grammar already implemented in Phase 0.
- ✅ Grammar defined in `sources/whatsapp/grammar.py`
- ✅ Used by parser for WhatsApp message format parsing
- No breaking changes for end users

---

## Phase 6: Agent Tools Refactoring

### File Reorganization

**BREAKING CHANGE**: WhatsApp-specific code moved from `ingestion/` to `sources/whatsapp/`.

**Before** (Phase 5):
```
ingestion/
├── grammar.py           # WhatsApp pyparsing grammar
├── parser.py            # WhatsApp export parsing
├── whatsapp_input.py    # WhatsApp InputSource
└── base.py              # Generic interfaces
```

**After** (Phase 6):
```
ingestion/
├── base.py              # Generic interfaces only
├── slack_input.py       # Slack source (future)
└── __init__.py          # Re-exports for compatibility

sources/
└── whatsapp/
    ├── grammar.py       # pyparsing grammar
    ├── parser.py        # WhatsApp parsing
    ├── input.py         # WhatsAppInputSource
    ├── models.py        # WhatsAppExport
    └── pipeline.py      # discover_chat_file()
```

**Migration**:
- ✅ Use re-exports: `from egregora.ingestion import parse_source` (works)
- ❌ Don't import directly: `from egregora.ingestion.parser import ...` (fails)
- ✅ Or import from source: `from egregora.sources.whatsapp.parser import parse_source`

### Function Renaming

**BREAKING CHANGE**: `parse_export` renamed to `parse_source`.

- ❌ OLD: `from egregora.ingestion import parse_export`
- ✅ NEW: `from egregora.ingestion import parse_source`

**Rationale**: More generic name, source-agnostic (not just "exports").

**Migration**:
```python
# Before
from egregora.ingestion import parse_export
table = parse_export(export, timezone=tz)

# After
from egregora.ingestion import parse_source
table = parse_source(export, timezone=tz)
```

---

## Migration Checklist

### For Library Users

1. **Update imports**:
   - Replace `parse_export` → `parse_source`
   - Use `from egregora.ingestion import ...` (not `from egregora.ingestion.parser`)

2. **Remove resume flags**:
   - Delete `--resume` from CLI commands
   - Delete `resume=True` from Python API calls

3. **Update function calls**:
   - If calling `write_posts_with_pydantic_agent`, bundle params into `config` and `context`
   - If calling `enrich_table`, bundle params into `EgregoraConfig` and `EnrichmentRuntimeContext`

4. **Clean up old data**:
   - Delete `.egregora/checkpoints/` (no longer used)
   - Delete `.egregora/enriched/` (no longer used)

### For Contributors

1. **Follow new patterns** (see CLAUDE.md):
   - Use `EgregoraConfig` instead of 10+ individual parameters
   - Use frozen dataclasses for runtime contexts
   - Simple resume logic (file existence checks)
   - Source-specific code in `sources/{source}/`

2. **Update tests**:
   - Import from `egregora.ingestion` (use re-exports)
   - Use `parse_source` instead of `parse_export`

3. **Never add**:
   - Functions with >5 parameters (use config objects)
   - Complex checkpoint systems (use simple file checks)
   - Backward compatibility shims (alpha mindset)

---

## Rollback Instructions

**Warning**: No rollback path. This is alpha development.

If you need the old behavior:
1. Git checkout before Phase 2: `git checkout <commit-before-phase-2>`
2. Or cherry-pick specific commits if you need features from both

---

## Timeline

- **Phase 0**: Config infrastructure (2024-12)
- **Phase 1**: Pydantic-AI patterns (2024-12)
- **Phase 2**: Configuration objects (2025-01-06)
- **Phase 3**: Pipeline decomposition (2025-01-07)
- **Phase 4**: CLI command decomposition (2025-01-07)
- **Phase 5**: Parser modernization (already complete in Phase 0)
- **Phase 6**: Agent tools refactoring (2025-01-07)
- **Phase 7**: Documentation and testing (2025-01-07)

---

## Questions?

See:
- `CLAUDE.md` for modern patterns and examples
- `CONTRIBUTING.md` for development guidelines
- Git commit messages for detailed rationale
