# Documentation Minimization Plan

**Goal**: Minimize manual documentation maintenance by maximizing automatic documentation generation via mkdocstrings.

**Status**: ✅ mkdocstrings already configured and working
**Branch**: `claude/minimize-docs-mkdocstring-9AaX1`

---

## Executive Summary

The Egregora project already has mkdocstrings configured and working well. Current usage shows 22+ mkdocstrings directives across V2 and Pure API documentation. The opportunity is to:

1. **Expand mkdocstrings coverage** to undocumented modules (CLI, agents, adapters, database)
2. **Remove redundant manual API docs** that duplicate what mkdocstrings generates
3. **Clean up leftover documentation** files
4. **Maintain architectural/conceptual docs** (these should stay manual)

**Estimated Impact**:
- Reduce manual API doc maintenance by ~70%
- Add automatic documentation for 150+ currently undocumented classes/functions
- Eliminate ~400+ lines of manually maintained API reference

---

## Current State Analysis

### ✅ What's Working Well

1. **mkdocstrings configuration** (mkdocs.yml:80-97)
   - Google-style docstrings
   - Proper Python handler setup
   - Good display options

2. **Existing mkdocstrings usage**:
   - Pure API reference (core.types, core.ports, core.config, repository)
   - V2 data primitives (Document, DocumentType, etc.)
   - V2 knowledge/RAG (VectorStore, RAG functions)
   - V2 configuration classes
   - V2 enrichment agents
   - V2 MkDocs scaffolding

3. **Config documentation generator**:
   - `/dev_tools/generate_config_docs.py` auto-generates config reference
   - Already in use for `/docs/getting-started/configuration.md`

4. **Code quality**:
   - Excellent Google-style docstrings throughout codebase
   - 200-300+ documentable classes/functions
   - Comprehensive examples and type hints

### ⚠️ Gaps & Opportunities

**Undocumented Modules** (can add mkdocstrings):
1. CLI commands (`cli/main.py`, `cli/read.py`) - ~400 lines of docstrings
2. Input adapters (WhatsApp, IPERON, self-reflection)
3. Agent modules (writer, reader, banner agents)
4. Database modules (DuckDB manager, ELO store, views)
5. Output adapters (beyond scaffolding)
6. Pipeline orchestration
7. Transformations (windowing, enrichment)
8. Exceptions (15+ custom exceptions in WhatsApp adapter alone)
9. Utils and helpers

**Redundant Manual Documentation**:
- Some manual API docs could be replaced entirely with mkdocstrings directives
- Need to identify which manual docs duplicate auto-generatable content

---

## Strategy: Phased Minimization Approach

### Phase 1: Quick Wins (High Impact, Low Effort)

**1.1 Add CLI Reference** ⭐ HIGH PRIORITY
- **Action**: Create `/docs/v2/api-reference/cli.md` with mkdocstrings directives
- **Coverage**: Main CLI, read command, all Typer commands
- **Impact**: Document ~400 lines of CLI docstrings automatically
- **Example directive**:
  ```markdown
  ::: egregora.cli.main
      options:
        show_root_heading: true
        heading_level: 2
  ```

**1.2 Add Exceptions Reference** ⭐ HIGH PRIORITY
- **Action**: Create `/docs/v2/api-reference/exceptions.md`
- **Coverage**: All custom exceptions across modules
- **Impact**: Document 20+ exception classes
- **Example**:
  ```markdown
  ::: egregora.input_adapters.whatsapp.exceptions
  ::: egregora.transformation.exceptions
  ::: egregora.output_sinks.exceptions
  ```

**1.3 Complete Input Adapters Documentation** ⭐ HIGH PRIORITY
- **Action**: Create `/docs/v2/api-reference/input-adapters.md`
- **Coverage**: WhatsApp, IPERON, self-reflection adapters
- **Impact**: Document 10+ adapter classes and 50+ methods
- **Example**:
  ```markdown
  ::: egregora.input_adapters.whatsapp.WhatsAppInputAdapter
  ::: egregora.input_adapters.iperon.IperonInputAdapter
  ::: egregora.input_adapters.self_reflection.SelfReflectionAdapter
  ```

**1.4 Expand Agent Documentation** ⭐ HIGH PRIORITY
- **Action**: Enhance `/docs/v2/api-reference/augmentation/enrichment.md`
- **Coverage**: Writer, reader, banner agents
- **Impact**: Document all Pydantic-AI agent classes
- **Example**:
  ```markdown
  ::: egregora.agents.writer
  ::: egregora.agents.reader
  ::: egregora.agents.banner
  ```

### Phase 2: Medium Priority (Comprehensive Coverage)

**2.1 Database Module Documentation**
- **Action**: Create `/docs/v2/api-reference/database.md`
- **Coverage**: DuckDB manager, ELO store, views, persistence
- **Example**:
  ```markdown
  ::: egregora.database.duckdb_manager
  ::: egregora.database.elo_store
  ::: egregora.database.views
  ```

**2.2 Pipeline Orchestration**
- **Action**: Create `/docs/v2/api-reference/pipeline.md`
- **Coverage**: Pipeline coordinator, execution logic
- **Example**:
  ```markdown
  ::: egregora.pipeline
  ```

**2.3 Transformations Documentation**
- **Action**: Create `/docs/v2/api-reference/transformations.md`
- **Coverage**: Windowing, enrichment, message processing
- **Example**:
  ```markdown
  ::: egregora.transformation.windowing
  ::: egregora.transformation.enrichment
  ```

**2.4 Output Adapters (Complete)**
- **Action**: Expand `/docs/v2/api-reference/output_sinks/`
- **Coverage**: All output adapters, not just scaffolding
- **Example**:
  ```markdown
  ::: egregora.output_sinks.mkdocs
  ::: egregora.output_sinks.static
  ```

**2.5 Config Overrides & Builders**
- **Action**: Add to existing config docs or create new file
- **Coverage**: Configuration builder classes
- **Example**:
  ```markdown
  ::: egregora.config.overrides
  ::: egregora.config.builder
  ```

### Phase 3: Cleanup & Consolidation

**3.1 Identify Redundant Manual Docs**
- **Action**: Review all `/docs/v2/api-reference/` files
- **Question**: Which manually written API docs can be deleted after adding mkdocstrings?
- **Method**:
  1. Check each manual API doc file
  2. Verify if mkdocstrings directive would cover the same content
  3. If yes, replace manual content with directive
  4. If manual content adds conceptual explanation, keep but minimize

**3.2 Remove Duplicate Content**
- **Criteria for removal**:
  - Pure API documentation (signatures, parameters, returns)
  - Content that exactly duplicates docstrings
  - Tables of classes/functions that mkdocstrings generates
- **Criteria to KEEP**:
  - Conceptual explanations
  - Architecture overviews
  - Usage guides and tutorials
  - Decision rationale

**3.3 Clean Up Leftover Files**
- **Check for**:
  - Old documentation versions (v1 docs if exist)
  - Orphaned .md files not in mkdocs.yml navigation
  - Duplicate content in multiple locations
  - Outdated documentation that references removed code

**3.4 Consolidate Navigation**
- **Action**: Update mkdocs.yml navigation structure
- **Goal**: Clear separation between:
  - **Guides** (conceptual, manual) - Architecture, getting started, tutorials
  - **API Reference** (auto-generated) - mkdocstrings directives
  - **Community** (manual) - Contributing, ADRs

---

## What To Keep Manual

**DO NOT convert these to mkdocstrings** (they should remain manual):

1. **Architecture Documentation** (`/docs/v2/architecture/`, `/docs/v3/architecture/`)
   - Protocols
   - URL conventions
   - System overviews
   - Design patterns

2. **Guides** (`/docs/v2/guides/`)
   - Privacy guide
   - Knowledge guide
   - Generation guide
   - UX vision/report

3. **Getting Started**
   - Installation
   - Deployment
   - Quickstart
   - Tutorials

4. **ADRs** (Architectural Decision Records)
   - Decision rationale and context
   - Keep all ADR files

5. **Community**
   - Contributing guide
   - Code of conduct
   - Governance

6. **Home/About Pages**
   - index.md
   - about.md

**Reason**: These are conceptual, tutorial, or process documentation that provides context beyond API reference.

---

## Implementation Checklist

### Phase 1: Quick Wins

- [ ] Create `/docs/v2/api-reference/cli.md` with CLI mkdocstrings directives
- [ ] Create `/docs/v2/api-reference/exceptions.md` with exception classes
- [ ] Create `/docs/v2/api-reference/input-adapters.md` with all adapters
- [ ] Enhance `/docs/v2/api-reference/augmentation/enrichment.md` with all agents
- [ ] Test local docs build: `mkdocs serve`
- [ ] Verify all mkdocstrings directives resolve correctly

### Phase 2: Comprehensive Coverage

- [ ] Create `/docs/v2/api-reference/database.md`
- [ ] Create `/docs/v2/api-reference/pipeline.md`
- [ ] Create `/docs/v2/api-reference/transformations.md`
- [ ] Expand output adapters documentation
- [ ] Add config overrides documentation
- [ ] Test local docs build again

### Phase 3: Cleanup

- [ ] Audit all existing `/docs/v2/api-reference/` files for redundancy
- [ ] Replace manual API docs with mkdocstrings where appropriate
- [ ] Remove or consolidate duplicate content
- [ ] Find and remove orphaned documentation files
- [ ] Update mkdocs.yml navigation structure
- [ ] Run final documentation build test
- [ ] Update contributing guide if documentation process changed

---

## Success Metrics

**Quantitative**:
- Reduce manual API doc lines by 70% (~280+ lines eliminated)
- Add automatic documentation for 150+ classes/functions
- Increase mkdocstrings directive count from 22 to 60+
- Reduce documentation files by 10-15 (consolidation)

**Qualitative**:
- API documentation always in sync with code
- Reduced maintenance burden on contributors
- Clear separation: guides (manual) vs API reference (auto)
- Better discoverability of all modules

---

## Risks & Mitigations

**Risk 1**: Over-reliance on mkdocstrings removes helpful context
- **Mitigation**: Keep introductory text in each API reference file
- **Example**: Brief overview paragraph before mkdocstrings directive

**Risk 2**: Docstrings may be incomplete or poor quality
- **Mitigation**: Audit shows existing docstrings are excellent (Google-style)
- **Action**: Fix any missing/poor docstrings in code (better long-term)

**Risk 3**: Breaking existing documentation links
- **Mitigation**: Keep file names similar, use redirects if needed
- **Action**: Search for internal links before removing files

**Risk 4**: Build failures if modules can't be imported
- **Mitigation**: Test locally with `mkdocs serve` after each change
- **Action**: Ensure all dependencies installed in docs build environment

---

## Next Steps

1. **Review & Approve This Plan**
2. **Start with Phase 1** (Quick Wins)
3. **Test incrementally** (build after each file added)
4. **Commit & push progress** regularly
5. **Create PR** when phases complete

---

## Questions for Review

Before starting implementation, please confirm:

1. ✅ **Scope**: Focus on Phase 1 (CLI, exceptions, input adapters, agents)?
2. ✅ **Approach**: Replace manual API docs with mkdocstrings where appropriate?
3. ✅ **Keep**: Architecture, guides, getting started docs stay manual?
4. ✅ **Cleanup**: Remove redundant/duplicate content in Phase 3?
5. ✅ **Timeline**: Should we tackle all phases or just Phase 1 for now?

---

**Plan created**: 2026-01-01
**Author**: Claude Code
**Branch**: claude/minimize-docs-mkdocstring-9AaX1

---

## Phase 3 Results: Cleanup & Consolidation

**Date**: 2026-01-01
**Status**: ✅ Completed

### Files Removed

**Redundant API Reference Files** (replaced by minimal mkdocstrings docs):
1. `docs/v2/api-reference/augmentation/enrichment.md` - Covered by agents.md
2. `docs/v2/api-reference/configuration.md` - Replaced by config.md
3. `docs/v2/api-reference/output_sinks/mkdocs/scaffolding.md` - Covered by output-adapters.md

**Orphaned/Obsolete Files**:
4. `docs/ux-vision.md` - Duplicate of v2/guides/ux-vision.md (in navigation)
5. `docs/v2/guides/privacy_readme.md` - Explains removed module, obsolete
6. `docs/v2/guides/ux-report.md` - Not in navigation, obsolete
7. `docs/v2/architecture/directory_structure.md` - Not in navigation, basic directory listing

**Empty Directories Removed**:
- `docs/v2/api-reference/augmentation/`
- `docs/v2/api-reference/output_sinks/mkdocs/`
- `docs/v2/api-reference/output_sinks/`

### Files Kept

**Planning/Development Docs** (not in nav, but useful):
- `docs/CLAUDE.md` - Developer notes
- `docs/jules_feedback_loop_plan.md` - Planning document
- All `docs/v3/` files - Future version planning (19 files)
- All `docs/adr/` files - Architectural Decision Records
- All `docs/demo/` files - Demo site content

### Final Documentation Structure

**Total markdown files**: 64 → 57 files (-7 files)

**API Reference files** (all minimal, auto-generated):
- 9 core API reference pages (cli, config, core, input-adapters, transformations, agents, pipeline, database, output-adapters, exceptions)
- Each file: 3-4 lines (title + single mkdocstrings directive)
- Legacy files (ingestion, privacy, knowledge): Still using mkdocstrings but not yet minimized

**Manual documentation** (kept as-is):
- Getting Started (4 files)
- Guides (4 files in nav)
- Architecture (3 files in nav)
- ADRs (8 files)
- About/Index pages

### Impact Summary

**Lines of Documentation Removed**: ~3,500+ lines
- Phase 1+2: 3,161 lines of manual API content
- Phase 3: ~340 lines from redundant files

**Maintenance Reduction**:
- 7 fewer files to maintain
- 3 empty directories removed
- All API reference now auto-generates from code docstrings
- Zero boilerplate - single directive per package

**Success Metrics**:
- ✅ 90%+ reduction in manual API documentation
- ✅ All new API pages use single package-level directive
- ✅ Orphaned/redundant files removed
- ✅ Documentation structure cleaned and organized

---

**Phase 3 completed**: 2026-01-01
**Final commit**: Coming next
