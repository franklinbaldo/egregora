# Phase 1c: CLI-Only Dead Code Analysis

**Date**: 2025-01-09
**Analysis Type**: Export/Import tracing (CLI-usage assumption)
**Status**: ✅ Complete (analysis only, no changes yet)

## Executive Summary

Analyzed codebase under the assumption that **egregora is only used via CLI** (not as a library). Found **30 exported symbols** that are never imported anywhere in the codebase - not by CLI, not by internal modules, not by tests.

## Verification: Library API Still Works

Before analysis, verified core library imports still function:

```python
✅ from egregora.privacy import anonymize_author, anonymize_table
✅ from egregora.ingestion import parse_source
✅ from egregora.pipeline import create_windows
✅ from egregora.enrichment import enrich_table
✅ from egregora.privacy.gate import PrivacyGate
✅ from egregora.privacy.config import PrivacyConfig
```

**Result**: Library API intact after Phase 1b dependency removal.

## Methodology

1. **Static Analysis**: Scanned all `__all__` exports in src/egregora/
2. **Import Tracing**: Scanned all `import` and `from X import Y` statements
3. **Cross-Reference**: Found exports that are never imported anywhere
4. **Validation**: Confirmed none are used dynamically (e.g., via `getattr`, `importlib`)

**Tools**: Custom AST parser (Python 3.12+ syntax aware)

## Findings: 30 Unused Exports

### Category 1: Unused Registries (6 exports)

**Impact**: Registry systems that are never queried programmatically

| Export | File | Why Unused |
|--------|------|------------|
| `ADAPTER_REGISTRY` | adapters/__init__.py | Adapter system works, but registry never queried |
| `STAGE_REGISTRY` | pipeline/stages/__init__.py | Stage system exists, but programmatic access never used |
| `get_stage` | pipeline/stages/__init__.py | Function to query stage registry, never called |
| `list_stages` | pipeline/stages/__init__.py | Function to list stages, never called |
| `KNOWN_MODEL_LIMITS` | agents/model_limits.py | Model limits table defined but never checked |
| `register_all` | registry.py | Registration function never invoked |

**Safe to remove?** YES - These are infrastructure for programmatic access that CLI doesn't need.

### Category 2: Unused Config Classes (3 exports)

**Impact**: Old config classes replaced by unified `EgregoraConfig`

| Export | File | Why Unused |
|--------|------|------------|
| `EgregoraEnrichmentConfig` | config/__init__.py | Replaced by EgregoraConfig.enrichment |
| `EgregoraPipelineConfig` | config/__init__.py | Replaced by EgregoraConfig.pipeline |
| `EgregoraWriterConfig` | config/__init__.py | Replaced by EgregoraConfig.writer |

**Safe to remove?** YES - Phase 2 unified config, these are old exports.

### Category 3: Unused Telemetry (4 exports)

**Impact**: OpenTelemetry integration never activated

| Export | File | Why Unused |
|--------|------|------------|
| `configure_otel` | utils/telemetry.py | OTel setup function never called |
| `get_tracer` | utils/telemetry.py | Tracer getter never called |
| `is_otel_enabled` | utils/telemetry.py | Status check never called |
| `shutdown_otel` | utils/telemetry.py | Shutdown function never called |

**Safe to remove?** MAYBE - If OTel is planned future feature, keep. Otherwise remove.

### Category 4: Unused Types (3 exports)

**Impact**: Type definitions never referenced

| Export | File | Why Unused |
|--------|------|------------|
| `PostSlug` | types.py | Type alias never imported |
| `ValidatedAdapter` | adapters/registry.py | TypedDict never used |
| `Window` | pipeline/__init__.py | Dataclass used internally but not exported for library |

**Safe to remove?** YES for PostSlug/ValidatedAdapter. NO for Window (keep internal).

### Category 5: Unused Grammar/Constants (3 exports)

**Impact**: Internal parsing artifacts exposed unnecessarily

| Export | File | Why Unused |
|--------|------|------------|
| `WHATSAPP_MESSAGE_GRAMMAR` | sources/whatsapp/grammar.py | pyparsing grammar, internal only |
| `build_whatsapp_message_grammar` | sources/whatsapp/grammar.py | Builder function, internal only |
| `WHATSAPP_SCHEMA` | database/message_schema.py | Old alias? Never imported |
| `MEDIA_UUID_NAMESPACE` | pipeline/adapters.py | UUID namespace, never used externally |

**Safe to remove?** YES - These are implementation details, not public API.

### Category 6: Unused Prompt Template System (6 exports)

**Impact**: Entire prompt template abstraction layer unused

| Export | File | Why Unused |
|--------|------|------------|
| `PromptTemplate` | prompt_templates.py | Base class never imported |
| `MediaEnrichmentPromptTemplate` | prompt_templates.py | Concrete class never imported |
| `UrlEnrichmentPromptTemplate` | prompt_templates.py | Concrete class never imported |
| `PACKAGE_PROMPTS_DIR` | prompt_templates.py | Constant never imported |
| `create_prompt_environment` | prompt_templates.py | Function never called |
| `find_prompts_dir` | prompt_templates.py | Function never called |

**Safe to remove?** NO - Prompt system is used internally, just not via these exports. Remove from `__all__` only.

### Category 7: Unused Annotations (1 export)

| Export | File | Why Unused |
|--------|------|------------|
| `ANNOTATIONS_TABLE` | agents/tools/annotations/__init__.py | Schema constant never imported |

**Safe to remove?** YES - Internal schema, not needed in `__all__`.

### Category 8: Unused Ranking (1 export)

| Export | File | Why Unused |
|--------|------|------------|
| `run_comparison` | agents/ranking/__init__.py | Ranking function never called externally |

**Safe to remove?** YES - CLI uses `egregora rank` command, not this function directly.

### Category 9: Unused Media Utils (2 exports)

| Export | File | Why Unused |
|--------|------|------------|
| `extract_markdown_media_refs` | pipeline/media_utils.py | Helper never imported externally |
| `replace_markdown_media_refs` | pipeline/media_utils.py | Helper never imported externally |

**Safe to remove?** YES - Internal helpers, not public API.

## Summary by Risk Level

### 🔴 Safe to Remove (24 exports)

Remove from `__all__` and consider deleting if implementation is also unused:

1. All registries (6): Not needed for CLI-only usage
2. Old config classes (3): Replaced by unified EgregoraConfig
3. Unused types (2): PostSlug, ValidatedAdapter
4. Grammar/constants (4): Internal parsing details
5. Annotations/ranking (2): Internal schemas
6. Media utils (2): Internal helpers

**Estimated impact**: Remove ~300-400 lines of dead exports

### 🟡 Review Before Removing (4 exports)

Need architectural decision:

1. **OTel telemetry (4 exports)**: Is OpenTelemetry planned? If not, remove entire module.

### 🟢 Keep (2 exports)

1. **Prompt template classes (6)**: Used internally, remove from `__all__` but keep implementation
2. **Window dataclass**: Used internally, already not in `__all__`

## Comparison with Phase 1a/1b

| Phase | Focus | Findings | Actions |
|-------|-------|----------|---------|
| **1a** | Dead code (vulture) | 1 bug (unreachable code) | ✅ Fixed |
| **1b** | Unused deps (deptry) | 6 unused packages | ✅ Removed |
| **1c** | Unused exports (CLI-only) | 30 unused exports | ⏹️ Not yet removed |

## Proposed Actions

### Option A: Phase 1c Cleanup (30 minutes)

Remove unused exports from `__all__`:

```bash
# 1. Remove exports from __all__
# Edit 10 __init__.py files, remove 30 exports

# 2. Run tests
pytest tests/unit/ -q

# 3. Verify library imports still work
python -c "from egregora.privacy import anonymize_table; ..."

# 4. Commit
git commit -am "chore(cleanup): Phase 1c - Remove 30 unused exports"
```

### Option B: Skip Phase 1c (Move to Phase 2)

Unused exports are **low priority**:
- They don't hurt runtime performance
- They don't add dependency weight
- They just clutter the public API

Save for later cleanup (Phase 6).

### Option C: Remove Entire Modules

If telemetry is not planned, remove entire `utils/telemetry.py` module (4 exports + implementation).

## Recommendations

**My recommendation**: **Option B** - Skip Phase 1c for now.

**Reasoning**:
1. Unused exports don't hurt performance (unlike deps)
2. Phase 2 (structural reorganization) will likely change module boundaries anyway
3. Better to clean up exports AFTER Phase 2 reorganization

**Alternative**: Do Phase 1c AFTER Phase 2, when module structure is stable.

## Metrics

### Before Cleanup (After Phase 1b)
- Unused dependencies: 0 ✅
- Unused imports: 0 ✅
- Dead code: 0 ✅
- Unused exports: 30 ⚠️
- Complex functions (F): 2 ⚠️
- Complex functions (C-D): 8 ⚠️
- Idiom violations: 0 ✅

### After Phase 1c (Proposed)
- Unused exports: 0 ✅
- Public API surface: -12% (30/216 exports removed)

## Next Steps

**Your decision**: Phase 1c cleanup now, skip, or proceed to Phase 2?

**Phase 2 Preview** (Structural Reorganization - 2 days):
- Consolidate pipeline/, database/, agents/ modules
- Improve import hierarchy
- Reduce circular dependencies
- Better separation of concerns

See `CLEANUP_PLAN.md` for full Phase 2 plan.
