# Code Consolidation Plan

**Status:** Planning Phase
**Created:** 2025-01-13
**Goal:** Consolidate duplicate files and clarify directory structure

## Executive Summary

Analysis of 91 Python files revealed significant redundancy and structural confusion:
- **7 MkDocs files** (should be 2-3)
- **8 enrichment files** (should be 3-4)
- **Multiple directory overlaps** with unclear boundaries
- **4 major name collision cases**

**Expected Impact:**
- Remove 10-15 redundant files
- Save ~50KB+ of duplicate code
- Significantly improve code clarity and onboarding time

---

## Phase 1: MkDocs Consolidation (HIGH PRIORITY)

### Current State (7 files)
```
output_adapters/
├── mkdocs.py                          (32KB) - Registry wrapper
├── mkdocs_output_adapter.py           (20KB) - Main implementation
├── mkdocs_site.py                     (13KB) - Site path resolution
├── mkdocs_storage.py                  (21KB) - Filesystem storage
├── legacy_mkdocs_url_convention.py    (5.9KB) - URL conventions
└── base.py                            (26KB) - Abstract base

storage/
├── output_adapter.py                  (5.4KB) - Protocol
└── url_convention.py                  (2.8KB) - URL abstraction
```

### Target State (Better Architecture)
```
data_primitives/
├── document.py                        - Document, DocumentType, DocumentCollection
├── base_types.py                      - GroupSlug, PostSlug
└── protocols.py                       - OutputAdapter, UrlConvention protocols (moved from storage/)

output_adapters/
├── base.py                            - Abstract base class (if needed for shared logic)
└── mkdocs/
    ├── __init__.py                    - Public exports
    ├── adapter.py                     - Main MkDocs implementation (merge mkdocs*.py)
    └── url_convention.py              - MkDocs-specific URL convention implementation
```

**Rationale:** `OutputAdapter` and `UrlConvention` are Protocol interfaces (Layer 1 abstractions)
that define fundamental contracts for working with Documents. They belong with other
data primitives, not in a directory named `storage/` which implies implementation.

### Steps

#### 1.0 Move protocols to data_primitives/ (ARCHITECTURAL IMPROVEMENT)
**File:** `data_primitives/protocols.py`

**Create new file with:**
- Move `OutputAdapter` protocol from `storage/output_adapter.py`
- Move `UrlConvention` protocol and `UrlContext` dataclass from `storage/url_convention.py`

**Update imports:**
```python
# OLD
from egregora.storage.output_adapter import OutputAdapter
from egregora.storage.url_convention import UrlConvention, UrlContext

# NEW
from egregora.data_primitives.protocols import OutputAdapter, UrlConvention, UrlContext
```

**Files to update:**
- `src/egregora/output_adapters/base.py`
- `src/egregora/output_adapters/mkdocs.py`
- `src/egregora/output_adapters/mkdocs_output_adapter.py`
- `src/egregora/output_adapters/hugo.py`
- `src/egregora/agents/writer/agent.py`
- `src/egregora/data_primitives/__init__.py` (add to exports)

**Delete empty directory:**
```bash
# After all protocols are moved
rm -rf src/egregora/storage/
```

#### 1.1 Create new mkdocs/ subdirectory
```bash
mkdir -p src/egregora/output_adapters/mkdocs
```

#### 1.2 Consolidate MkDocs implementation
**File:** `output_adapters/mkdocs/adapter.py`

**Merge from:**
- `mkdocs_output_adapter.py` (main implementation) - BASE
- `mkdocs.py` (registry wrapper) - Add factory methods
- `mkdocs_site.py` (site resolution) - Add as helper functions
- `mkdocs_storage.py` (filesystem storage) - Add as methods

**Keep separate:**
- `base.py` - Abstract base class (used by other adapters)
- `legacy_mkdocs_url_convention.py` → rename to `mkdocs/url_convention.py`

#### 1.3 Update imports across codebase
```python
# OLD
from egregora.output_adapters.mkdocs import MkDocsOutputAdapter
from egregora.output_adapters.mkdocs_output_adapter import MkDocsOutputAdapter
from egregora.output_adapters.mkdocs_site import resolve_site_paths

# NEW
from egregora.output_adapters.mkdocs import MkDocsOutputAdapter, resolve_site_paths
```

**Files to update:**
- `src/egregora/agents/writer/writer_runner.py`
- `src/egregora/orchestration/write_pipeline.py`
- `src/egregora/init/scaffolding.py`
- `src/egregora/config/__init__.py`

#### 1.4 Testing
```bash
# Run full test suite
uv run pytest tests/unit/storage/
uv run pytest tests/unit/test_abstraction_layer.py
uv run pytest tests/integration/ -k mkdocs

# Verify no regressions
uv run pytest tests/
```

#### 1.5 Cleanup
```bash
# Remove old files
rm src/egregora/output_adapters/mkdocs.py
rm src/egregora/output_adapters/mkdocs_output_adapter.py
rm src/egregora/output_adapters/mkdocs_site.py
rm src/egregora/output_adapters/mkdocs_storage.py
rm src/egregora/output_adapters/legacy_mkdocs_url_convention.py
```

**Estimated Time:** 4-6 hours
**Risk:** Medium (affects core functionality)
**Benefit:** Removes 5 files, ~40KB code reduction, much clearer structure

---

## Phase 2: Enrichment Consolidation (HIGH PRIORITY)

### Current State (8 files)
```
enrichment/
├── agents.py              (185 lines) - Pydantic AI agents
├── thin_agents.py         (218 lines) - Thin pydantic-ai agents (71% similar!)
├── simple_runner.py       (626 lines) - Straight-loop runner
├── batch.py               (165 lines) - Batch processing
├── core.py                (81 lines) - Core enrichment
├── media.py               (217 lines) - Media enrichment
├── avatar.py              (427 lines) - Avatar download
└── avatar_pipeline.py     (306 lines) - Avatar pipeline (57% similar)
```

### Target State (4 files)
```
enrichment/
├── agents.py              - All Pydantic AI agent implementations
├── runners.py             - All runner implementations (simple, batch, core)
├── avatar.py              - Avatar download, validation, and pipeline
└── media.py               - Media enrichment (keep as-is)
```

### Steps

#### 2.1 Consolidate agent implementations
**File:** `enrichment/agents.py`

**Merge from:**
- `agents.py` (BASE - keep structure)
- `thin_agents.py` (71% similar - add thin agent variants)

**Strategy:**
```python
# Keep both patterns available, clearly documented
def create_url_enrichment_agent(...):  # Full agent
    """Full Pydantic AI agent for URL enrichment."""

def create_thin_url_enrichment_agent(...):  # Thin variant
    """Lightweight single-call agent for URL enrichment."""
```

#### 2.2 Consolidate runner implementations
**File:** `enrichment/runners.py`

**Merge from:**
- `simple_runner.py` (BASE - main runner)
- `batch.py` (add batch processing logic)
- `core.py` (add core utilities)

**Keep public API:**
```python
# Main entry point
def enrich_table(...) -> Table:
    """Enrich table with LLM-powered context (simple runner)."""

# Batch variant
def enrich_table_batch(...) -> Table:
    """Enrich table using Gemini Batch API."""
```

#### 2.3 Consolidate avatar functionality
**File:** `enrichment/avatar.py`

**Merge from:**
- `avatar.py` (BASE - download/validation)
- `avatar_pipeline.py` (add pipeline integration)

**Structure:**
```python
# Low-level functions
async def download_avatar(...) -> bytes:
    """Download and validate avatar image."""

# High-level pipeline
def process_avatar_commands(...) -> dict:
    """Process /egregora avatar commands from messages."""
```

#### 2.4 Update imports
**Files to update:**
- `src/egregora/orchestration/write_pipeline.py`
- `src/egregora/enrichment/__init__.py`
- Any tests in `tests/unit/enrichment/`
- Any tests in `tests/integration/`

#### 2.5 Testing
```bash
uv run pytest tests/unit/enrichment/
uv run pytest tests/integration/ -k enrichment
```

#### 2.6 Cleanup
```bash
rm src/egregora/enrichment/thin_agents.py
rm src/egregora/enrichment/simple_runner.py
rm src/egregora/enrichment/batch.py
rm src/egregora/enrichment/core.py
rm src/egregora/enrichment/avatar_pipeline.py
```

**Estimated Time:** 3-4 hours
**Risk:** Medium (enrichment is actively used)
**Benefit:** Removes 5 files, clearer organization

---

## Phase 3: Name Collision Resolution (MEDIUM PRIORITY)

### Issue 3.1: batch.py collision

**Current:**
- `enrichment/batch.py` - Enrichment batch processing
- `utils/batch.py` - Gemini Batch API helpers

**Resolution:**
After Phase 2, `enrichment/batch.py` will be merged into `enrichment/runners.py`.
No further action needed.

### Issue 3.2: constants.py collision

**Current:**
- `constants.py` - "Central location for all constants"
- `privacy/uuid_namespaces.py` - "Frozen UUID5 namespaces" (renamed from `privacy/constants.py`)

**Resolution:**
Ensure all imports reference the new module name:
```python
from egregora.privacy.uuid_namespaces import NAMESPACE_AUTHOR
```

**Files to update:**
- Any modules, tests, or docs importing from `egregora.privacy.constants`

### Issue 3.3: validation.py collision

**Current:**
- `config/config_validation.py` - Configuration validation utilities (renamed from `config/validation.py`)
- `database/validation.py` - Schema validation

**Resolution:**
Update imports to use the new module name:
```python
from egregora.config.config_validation import parse_date_arg
```

**Files to update:**
- CLI modules or helpers importing `egregora.config.validation`

### Issue 3.4: media.py collision

**Current:**
- `enrichment/media.py` - Media enrichment (LLM descriptions)
- `transformations/media.py` - Media extraction/processing

**Analysis:**
These files have **different purposes**:
- `enrichment/media.py` - Adds LLM-powered context to media
- `transformations/media.py` - Extracts media refs from messages

**Resolution:**
Keep both, but add clear docstrings:
```python
# enrichment/media.py
"""Media enrichment: Add LLM-generated descriptions to images/videos.

This module uses vision models to describe media content for accessibility
and context. Called during the enrichment stage of the pipeline.
"""

# transformations/media.py
"""Media extraction: Extract media references from messages.

This module finds media attachments in chat messages and prepares them
for processing. Called during the transformation stage of the pipeline.
"""
```

**Estimated Time:** 1-2 hours
**Risk:** Low (mostly renames)
**Benefit:** Clearer naming, reduced confusion

---

## Phase 4: Directory Structure Clarification (MEDIUM PRIORITY)

### Issue 4.1: sources/ vs input_adapters/ overlap

**Current Structure:**
```
sources/
├── base.py              - InputAdapter protocol
└── whatsapp/
    ├── grammar.py       - Parser grammar
    ├── models.py        - Data models
    ├── parser.py        - Message parsing
    └── pipeline.py      - Pipeline functions (⚠️ misplaced)

input_adapters/
├── whatsapp.py         - WhatsAppAdapter implementation
├── slack.py            - SlackAdapter implementation
└── registry.py         - Adapter registry
```

**Problem:**
- Protocol defined in `sources/` but implementations in `input_adapters/`
- Parsing logic in `sources/whatsapp/` but adapter wrapper in `input_adapters/`
- Pipeline functions in wrong location

**Target Structure (Option A - Consolidate into input_adapters/):**
```
input_adapters/
├── base.py              - InputAdapter protocol (moved from sources/)
├── registry.py          - Adapter registry
├── whatsapp/
│   ├── __init__.py      - WhatsAppAdapter (public API)
│   ├── grammar.py       - Parser grammar
│   ├── models.py        - Data models
│   └── parser.py        - Message parsing
└── slack/
    ├── __init__.py      - SlackAdapter
    └── parser.py        - Slack parsing logic
```

**Steps:**

1. Move `sources/base.py` to `input_adapters/base.py`
2. Move `sources/whatsapp/` contents into `input_adapters/whatsapp/`
3. Merge `input_adapters/whatsapp.py` into `input_adapters/whatsapp/__init__.py`
4. Move pipeline functions from `sources/whatsapp/pipeline.py` to `orchestration/`
5. Update all imports across codebase
6. Delete `sources/` directory

**Import updates:**
```python
# OLD
from egregora.sources.base import InputAdapter
from egregora.sources.whatsapp.parser import parse_whatsapp_export

# NEW
from egregora.input_adapters.base import InputAdapter
from egregora.input_adapters.whatsapp import WhatsAppAdapter
```

**Estimated Time:** 3-4 hours
**Risk:** Medium (lots of import updates)
**Benefit:** Clear directory structure, removes directory overlap

### Issue 4.2: storage/ directory removal

**Resolution:** ✅ COMPLETED IN PHASE 1

The `storage/` directory is eliminated entirely in Phase 1.0, with protocols moved
to `data_primitives/protocols.py` where they belong as foundational abstractions.

This resolves the confusion about whether `storage/` contains protocols or implementations.

---

## Phase 5: Pipeline Logic Consolidation (LOW PRIORITY)

### Issue: Pipeline logic scattered

**Current:**
- `orchestration/write_pipeline.py` - Main write pipeline
- `sources/whatsapp/pipeline.py` - WhatsApp-specific pipeline functions

**Resolution:**
Move WhatsApp pipeline functions to orchestration:

```bash
# Review sources/whatsapp/pipeline.py
# Extract reusable functions, move to orchestration/write_pipeline.py
# Delete sources/whatsapp/pipeline.py
```

**Estimated Time:** 2 hours
**Risk:** Low
**Benefit:** All pipeline logic in one place

---

## Testing Strategy

### Unit Tests
After each phase, run relevant unit tests:
```bash
# Phase 1 - MkDocs
uv run pytest tests/unit/storage/ -v
uv run pytest tests/unit/test_abstraction_layer.py -v

# Phase 2 - Enrichment
uv run pytest tests/unit/enrichment/ -v

# Phase 3 - Renames
uv run pytest tests/unit/config/ -v
uv run pytest tests/unit/privacy/ -v

# Phase 4 - Directory structure
uv run pytest tests/unit/test_adapters.py -v
uv run pytest tests/unit/test_adapter_registry.py -v
```

### Integration Tests
```bash
# After each phase
uv run pytest tests/integration/ -v

# Full pipeline test
uv run pytest tests/e2e/ -v
```

### Manual Testing
```bash
# Test CLI commands still work
uv run egregora doctor
uv run egregora views list
uv run egregora runs tail

# Test with sample data (if available)
uv run egregora write sample_export.zip --output test_output
```

---

## Risk Mitigation

### Before Starting
1. ✅ Create feature branch: `git checkout -b refactor/consolidation`
2. ✅ Ensure all tests pass: `uv run pytest tests/`
3. ✅ Create backup: `git tag pre-consolidation`

### During Each Phase
1. Work in small commits (one file at a time)
2. Run tests after each change
3. Keep detailed notes of changes
4. Review diffs carefully before committing

### Rollback Plan
If tests fail after a phase:
```bash
# Revert to last working state
git reset --hard <last-good-commit>

# Or revert specific changes
git revert <problematic-commit>
```

---

## Success Metrics

### Quantitative
- [ ] Reduce Python file count from 91 to ~75-80
- [ ] Remove ~50KB+ of duplicate code
- [ ] Reduce MkDocs files from 7 to 3
- [ ] Reduce enrichment files from 8 to 4
- [ ] Eliminate 4 name collision cases
- [ ] All tests passing (401+ tests)

### Qualitative
- [ ] Clearer directory structure
- [ ] Easier onboarding for new developers
- [ ] Reduced cognitive load when navigating codebase
- [ ] Clear separation of protocols vs implementations
- [ ] No confusion about where to add new features

---

## Timeline Estimate

| Phase | Time | Complexity | Dependencies |
|-------|------|------------|--------------|
| Phase 1: MkDocs + Protocols | 5-7 hrs | Medium-High | None |
| Phase 2: Enrichment | 3-4 hrs | Medium | Phase 1 |
| Phase 3: Name Collisions | 1-2 hrs | Low | Phase 2 |
| Phase 4: Directory Structure | 3-4 hrs | Medium | Phase 3 |
| Phase 5: Pipeline Logic | 2 hrs | Low | Phase 4 |
| **Total** | **14-19 hrs** | | |

**Note:** Phase 1 now includes moving protocols to `data_primitives/`, which improves
architectural clarity and eliminates the `storage/` directory entirely.

**Recommended approach:** Complete Phase 1-3 in one sprint, Phase 4-5 in next sprint.

---

## Approval Checklist

Before executing:
- [ ] Review plan with team/maintainers
- [ ] Confirm priority order
- [ ] Ensure test coverage is adequate
- [ ] Set up monitoring for regression detection
- [ ] Allocate sufficient time for testing and review

---

## References

- Analysis report: `/tmp/final_report.md`
- Duplicate detection script: `/tmp/analyze_duplicates.py`
- Current branch: `claude/cleanup-dead-code-011CV5iNFbtV6m2ysJA1mvhV`
