# Egregora Documentation Rebuild Plan

**Date:** 2025-11-18
**Status:** Planning
**Priority:** P0 - Documentation is currently broken

## Current State Analysis

### Problems Identified

1. **Outdated module references** - Docs reference modules that don't exist:
   - `egregora.enrichment.core` → should be `egregora.enrichment.runners`
   - `egregora.agents.tools.profiler` → should be `egregora.agents.shared.author_profiles`
   - `egregora.models` → should be `egregora.data_primitives`

2. **Misaligned API docs** - Don't match current codebase structure:
   - Module reorganization not reflected (core → data_primitives, rendering → output_adapters, etc.)
   - Many placeholder/empty documentation files
   - Navigation structure doesn't match actual code organization

3. **Build failures** - `mkdocs serve` fails due to missing modules in mkdocstrings references

4. **Stale content** - Many docs in `docs/` directory not included in navigation

## Proposed Documentation Structure

### Phase 1: Core Documentation (User-Facing)
**Priority: P0 - Essential for users**

#### 1. Home & Getting Started

```
docs/
├── index.md                          # Overview, value proposition, quick example
└── getting-started/
    ├── installation.md               # Installation with uv
    ├── quickstart.md                 # End-to-end example with real WhatsApp export
    └── configuration.md              # Config file, env vars, model settings
```

**Content Sources:**
- `CLAUDE.md` - Technical details, recent changes, architecture
- `README.md` - User-facing overview
- Existing `getting-started/` files (if salvageable)

#### 2. User Guide (Conceptual)

```
docs/guide/
├── architecture.md                   # Staged pipeline overview, data flow diagram
├── privacy.md                        # Anonymization, PII detection, privacy-first design
├── knowledge.md                      # RAG, chunking, embeddings, retrieval modes
└── generation.md                     # Writer agent, prompts, journal entries, thinking
```

**Focus:**
- Explain concepts, not implementation details
- Include Mermaid diagrams for pipeline stages
- Real-world examples and use cases

### Phase 2: API Reference (Auto-Generated)
**Priority: P1 - Important for developers**

Map to **actual codebase structure** (validated against `src/egregora/`):

#### Input & Ingestion

```
docs/api/input-adapters/
├── index.md                          # InputAdapter protocol overview
├── whatsapp.md                       # ::: egregora.input_adapters.whatsapp
└── slack.md                          # ::: egregora.input_adapters.slack
```

#### Privacy

```
docs/api/privacy/
├── index.md                          # Privacy-first architecture overview
├── anonymizer.md                     # ::: egregora.privacy.anonymizer
├── detector.md                       # ::: egregora.privacy.detector
└── gate.md                           # ::: egregora.privacy.gate
```

#### Enrichment

```
docs/api/enrichment/
├── index.md                          # LLM enrichment overview
├── runners.md                        # ::: egregora.enrichment.runners
├── media.md                          # ::: egregora.enrichment.media
└── avatar.md                         # ::: egregora.enrichment.avatar
```

#### Agents

```
docs/api/agents/
├── index.md                          # Agent architecture overview
├── writer.md                         # ::: egregora.agents.writer
├── reader.md                         # ::: egregora.agents.reader
└── shared/
    ├── profiles.md                   # ::: egregora.agents.shared.author_profiles
    └── rag.md                        # ::: egregora.agents.shared.rag
```

#### Data & Database

```
docs/api/data-primitives/
├── index.md                          # Foundation layer overview
├── document.md                       # ::: egregora.data_primitives.document
└── types.md                          # ::: egregora.data_primitives.base_types

docs/api/database/
├── index.md                          # Database layer overview
├── schema.md                         # ::: egregora.database.ir_schema
├── manager.md                        # ::: egregora.database.duckdb_manager
└── views.md                          # ::: egregora.database.views
```

#### Transformations

```
docs/api/transformations/
├── index.md                          # Pure functional transforms overview
├── windowing.md                      # ::: egregora.transformations.windowing
└── media.md                          # ::: egregora.transformations.media
```

#### Output

```
docs/api/output-adapters/
├── index.md                          # OutputAdapter protocol overview
├── mkdocs.md                         # ::: egregora.output_adapters.mkdocs
└── hugo.md                           # ::: egregora.output_adapters.hugo
```

#### Orchestration

```
docs/api/orchestration/
├── index.md                          # Workflow orchestration overview
└── write-pipeline.md                 # ::: egregora.orchestration.write_pipeline

docs/api/cli/
├── index.md                          # CLI overview
└── main.md                           # ::: egregora.cli
```

### Phase 3: Development Documentation
**Priority: P2 - Nice to have**

```
docs/development/
├── contributing.md                   # Contribution guidelines, TENET-BREAK philosophy
├── testing.md                        # VCR cassettes, fixtures, test patterns
└── structure.md                      # Three-layer architecture, functional transforms
```

## Implementation Strategy

### Step 1: Audit & Clean
**Goal:** Remove outdated content, preserve useful reference material

**Tasks:**
- [ ] Create `docs/archive/` directory
- [ ] Move outdated/broken docs to archive:
  - All current `api/` files with wrong module paths
  - Outdated planning docs (REFACTORING_PLAN.md, etc.)
  - Duplicate/stale content
- [ ] Keep only:
  - `CLAUDE.md` (root)
  - `README.md` (root)
  - `includes/abbreviations.md` (referenced by mkdocs config)
  - Essential reference docs

**Commands:**
```bash
cd /home/user/workspace/egregora
mkdir -p docs/archive
# Move outdated files (to be scripted)
```

### Step 2: Write Core User Docs (Manual)
**Goal:** Essential documentation for users to get started

**Priority Order:**
1. `docs/index.md` - Home page
2. `docs/getting-started/installation.md`
3. `docs/getting-started/quickstart.md`
4. `docs/getting-started/configuration.md`
5. `docs/guide/architecture.md` (with Mermaid diagram)
6. `docs/guide/privacy.md`
7. `docs/guide/knowledge.md`
8. `docs/guide/generation.md`

**Content Sources:**
- Extract from `CLAUDE.md` (technical details, architecture)
- Extract from `README.md` (user-facing overview)
- Create new diagrams for pipeline stages

**Quality Criteria:**
- New user can go from zero to running pipeline
- Each concept explained before use
- Examples use real data (real-whatsapp-export.zip)

### Step 3: Generate API Reference (Automated)
**Goal:** Accurate, auto-generated API docs from docstrings

**Process:**
1. For each module in codebase:
   - Verify module exists: `python -c "import egregora.X.Y"`
   - Create minimal doc file with `:::` reference
   - Add brief intro paragraph
2. Create index.md for each section explaining the layer
3. Test each file individually before adding to nav

**Template:**
```markdown
# [Module Name]

Brief description of what this module does.

::: egregora.module.path
    options:
      show_source: true
      show_root_heading: true
```

**Validation:**
```bash
# Test each module imports successfully
.venv/bin/mkdocs build --strict
```

### Step 4: Update Navigation
**Goal:** Clean, logical navigation structure

**New mkdocs.yml nav:**
```yaml
nav:
  - Home: index.md
  - Getting Started:
    - Installation: getting-started/installation.md
    - Quick Start: getting-started/quickstart.md
    - Configuration: getting-started/configuration.md
  - User Guide:
    - Architecture: guide/architecture.md
    - Privacy & Anonymization: guide/privacy.md
    - Knowledge & RAG: guide/knowledge.md
    - Content Generation: guide/generation.md
  - API Reference:
    - Overview: api/index.md
    - Input Adapters: api/input-adapters/index.md
    - Privacy: api/privacy/index.md
    - Enrichment: api/enrichment/index.md
    - Agents: api/agents/index.md
    - Data Primitives: api/data-primitives/index.md
    - Database: api/database/index.md
    - Transformations: api/transformations/index.md
    - Output Adapters: api/output-adapters/index.md
    - Orchestration: api/orchestration/index.md
    - CLI: api/cli/index.md
  - Development:
    - Contributing: development/contributing.md
    - Testing: development/testing.md
    - Project Structure: development/structure.md
```

### Step 5: Verify & Deploy
**Goal:** Ensure docs build and serve correctly

**Checklist:**
- [ ] `mkdocs serve` runs without errors
- [ ] All internal links resolve
- [ ] All mkdocstrings imports succeed
- [ ] No broken images/diagrams
- [ ] Navigation is logical and complete
- [ ] Mobile-friendly (Material theme responsive)

**Commands:**
```bash
# Local verification
.venv/bin/mkdocs serve
# Visit http://localhost:8000 and test all pages

# Build for deployment
.venv/bin/mkdocs build --strict

# Deploy to GitHub Pages (when ready)
.venv/bin/mkdocs gh-deploy
```

## Success Criteria

**Must Have:**
- [x] `mkdocs serve` runs without errors ✅
- [ ] All API references point to valid Python modules
- [ ] User can go from zero to running pipeline using docs alone
- [ ] Architecture diagrams explain staged pipeline clearly
- [ ] All mkdocstrings imports succeed

**Nice to Have:**
- [ ] Screenshots of CLI output
- [ ] Interactive code examples
- [ ] Troubleshooting section
- [ ] FAQ page

## Estimated Scope

### Files to Archive/Delete
Approximately **40-50 outdated files** to move to `docs/archive/`:
- Current `api/` directory (wrong paths)
- Planning docs (REFACTORING_PLAN.md, ROADMAP_SUMMARY.md, etc.)
- Outdated development docs

### Files to Create

**Manual (from scratch):**
- ~12 user-facing pages (index + Getting Started + User Guide)

**Auto-generated:**
- ~25 API reference pages (minimal content + mkdocstrings)

**Update:**
- 1 `mkdocs.yml` (major nav restructure)

### Estimated Effort
- **Step 1 (Audit):** 30 minutes
- **Step 2 (User Docs):** 3-4 hours
- **Step 3 (API Ref):** 2 hours
- **Step 4 (Navigation):** 30 minutes
- **Step 5 (Verify):** 1 hour

**Total:** ~7 hours for complete rebuild

## Next Steps

1. Get approval for plan
2. Execute Step 1 (archive old docs)
3. Create fresh structure with placeholders
4. Write docs in priority order
5. Iterate until `mkdocs serve` succeeds

## Notes

- Keep `docs/overrides/`, `docs/stylesheets/`, `docs/javascripts/` unchanged (theme customization)
- Preserve `includes/abbreviations.md` (used by pymdownx.snippets)
- All Mermaid diagrams should be embedded (not external files)
- Use existing mkdocs.yml plugins (don't remove mkdocstrings, etc.)

## References

- Current codebase structure: `src/egregora/`
- CLAUDE.md: Architecture, recent changes, conventions
- README.md: User-facing project overview
- Existing good examples: (none identified yet - starting fresh)
