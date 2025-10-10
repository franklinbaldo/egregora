# 🌳 Egregora Project Pruning Plan

**Version**: 1.0  
**Date**: October 9, 2025  
**Project**: franklinbaldo-egregora  
**Goal**: Reduce codebase complexity by 30-40% while maintaining core functionality

---

## 📋 Executive Summary

This plan identifies **58 files** and **3 directories** for potential removal, organized by priority and impact. Following this plan will:

- ✂️ **Remove ~35-40% of codebase** (deprecated tests, redundant workflows, unused features)
- 🚀 **Simplify maintenance** (fewer CI workflows, consolidated tests)
- 🧹 **Clean dependencies** (remove unused packages from pyproject.toml)
- ⚡ **Improve focus** (keep only production-critical code)

---

## 🎯 Pruning Strategy

### Phase 1: Safe Removals (No Risk)
Remove clearly unused/deprecated files with zero production impact.

### Phase 2: Feature Evaluation (Low Risk)
Remove optional features you're not actively using.

### Phase 3: Test Consolidation (Medium Risk)
Merge and simplify test files while maintaining coverage.

---

## 📊 File Categorization

### LEGEND
- 🔴 **REMOVE** - Safe to delete immediately
- 🟡 **REVIEW** - Evaluate if still needed
- 🟢 **KEEP** - Essential for core functionality
- 🔵 **CONSOLIDATE** - Merge with similar files

---

## 🔴 PHASE 1: Safe Removals (Immediate)

### GitHub Workflows - Remove 4 of 6 workflows

**REMOVE** ❌
```bash
.github/workflows/claude-code-review.yml
.github/workflows/claude.yml
.github/workflows/manual-claude-review.yml
.github/workflows/pr-codex-review.yml
```

**KEEP** ✅
```bash
.github/workflows/ci.yml                    # Core CI pipeline
.github/workflows/gh-pages.yml              # Documentation (if using)
```

**Rationale**: You have 4 overlapping Claude/Codex review workflows. Keep only `ci.yml` for basic CI. Keep `gh-pages.yml` only if you're publishing documentation.

**Commands**:
```bash
# Remove redundant review workflows
rm .github/workflows/claude-code-review.yml
rm .github/workflows/claude.yml
rm .github/workflows/manual-claude-review.yml
rm .github/workflows/pr-codex-review.yml

# If not using GitHub Pages documentation:
rm .github/workflows/gh-pages.yml
```

---

### GitHub Scripts - Remove review automation

**REMOVE** ❌
```bash
.github/scripts/claude-review.py
```

**Rationale**: This script supports the removed CI workflows.

**Commands**:
```bash
rm .github/scripts/claude-review.py
rmdir .github/scripts  # Remove empty directory
```

---

### Test Files - Remove 11 deprecated/redundant tests

**REMOVE** ❌
```bash
tests/test_rag_search_deprecated.py         # Marked as deprecated
tests/test_enrichment.py                    # Superseded by _simple variant
tests/test_enrichment_dataframe.py          # Specialized variant
tests/test_enrichment_with_cache.py         # Specialized variant
tests/test_rag_llamaindex.py                # LlamaIndex-specific (if not using)
tests/test_process_backlog_smoke.py         # Smoke test for removed script
tests/test_url_preservation.py              # Likely covered in other tests
tests/test_date_utils.py                    # Utils test (low value)
tests/test_merge_config.py                  # Config test (low value)
tests/test_prompt_loading.py                # Prompt test (low value)
tests/run_all_tests.py                      # Use pytest instead
```

**KEEP** ✅
```bash
tests/test_core_pipeline.py                 # Core functionality
tests/test_enrichment_simple.py             # Primary enrichment tests
tests/test_newsletter_simple.py             # Primary newsletter tests
tests/test_whatsapp_integration.py          # WhatsApp-specific tests
tests/test_rag_integration.py               # RAG system tests
tests/test_privacy_e2e.py                   # Privacy/anonymization
tests/test_mcp_server.py                    # MCP server (if keeping feature)
tests/test_media_extractor.py               # Media extraction (if keeping)
tests/test_analytics.py                     # Analytics (if keeping)
```

**Rationale**: Remove deprecated tests, specialized variants, and low-value utility tests. Keep comprehensive end-to-end tests.

**Commands**:
```bash
# Remove deprecated and redundant tests
rm tests/test_rag_search_deprecated.py
rm tests/test_enrichment.py
rm tests/test_enrichment_dataframe.py
rm tests/test_enrichment_with_cache.py
rm tests/test_rag_llamaindex.py
rm tests/test_process_backlog_smoke.py
rm tests/test_url_preservation.py
rm tests/test_date_utils.py
rm tests/test_merge_config.py
rm tests/test_prompt_loading.py
rm tests/run_all_tests.py
```

---

### Test Stubs - Remove if not actively using

**REMOVE** ❌
```bash
tests/stubs/google/genai/__init__.py
tests/stubs/google/genai/types.py
tests/stubs/google/__init__.py
```

**Rationale**: Type stubs for Google GenAI. Only needed if you have type checking errors without them.

**Commands**:
```bash
# Remove type stubs (test if you need them first)
rm -rf tests/stubs/
```

---

### Example & Documentation Files

**REMOVE** ❌
```bash
example_enrichment.py                       # Example code, not production
TESTING_PLAN.md                             # 200+ lines of test documentation
AGENTS.md                                   # Agent documentation
.github/copilot-instructions.md             # Copilot instructions
.github/PULL_REQUEST_TEMPLATE.md            # PR template (if not using)
```

**Rationale**: Example files and extensive documentation are useful initially but bloat production repos.

**Commands**:
```bash
rm example_enrichment.py
rm TESTING_PLAN.md
rm AGENTS.md
rm .github/copilot-instructions.md

# If you don't use PR templates:
rm .github/PULL_REQUEST_TEMPLATE.md
```

---

### Configuration Files - Remove linting/formatting tools

**REMOVE** ❌
```bash
.codespellrc                                # Spell checking config
codespell_targets.txt                       # Spell checking targets
.markdownlint-cli2.jsonc                    # Markdown linting
.pre-commit-config.yaml                     # Pre-commit hooks
```

**Rationale**: Linting/formatting tools are great for development but not required for production. If you're the sole developer, these add maintenance overhead.

**Commands**:
```bash
rm .codespellrc
rm codespell_targets.txt
rm .markdownlint-cli2.jsonc
rm .pre-commit-config.yaml
```

---

### Metrics & Data Files

**REMOVE** ❌
```bash
metrics/enrichment_run.csv                  # Historical metrics data
```

**Rationale**: Old metrics data. Archive elsewhere if needed.

**Commands**:
```bash
rm metrics/enrichment_run.csv
rmdir metrics  # Remove empty directory
```

---

## 🟡 PHASE 2: Feature Evaluation (Review Before Removing)

### MCP Server (Model Context Protocol)

**LOCATION**: `src/egregora/mcp_server/`

**FILES**:
```bash
src/egregora/mcp_server/__init__.py
src/egregora/mcp_server/config.py
src/egregora/mcp_server/server.py
src/egregora/mcp_server/tools.py
scripts/start_mcp_server.py
tests/test_mcp_server.py
```

**QUESTION**: Are you using MCP integration to expose Egregora as a tool for LLMs?

**IF NO** → Remove all MCP-related files:
```bash
rm -rf src/egregora/mcp_server/
rm scripts/start_mcp_server.py
rm tests/test_mcp_server.py
```

**IMPACT**: Removes ~600-800 lines of code related to MCP protocol implementation.

---

### Remote Source Sync

**LOCATION**: `src/egregora/`

**FILES**:
```bash
src/egregora/remote_source.py
src/egregora/remote_sync.py
tests/test_remote_source_config.py
tests/test_remote_source_sync.py
tests/test_cli_sync.py
```

**QUESTION**: Do you need to sync conversations from remote sources, or do you only process local WhatsApp exports?

**IF LOCAL ONLY** → Remove remote sync features:
```bash
rm src/egregora/remote_source.py
rm src/egregora/remote_sync.py
rm tests/test_remote_source_config.py
rm tests/test_remote_source_sync.py
rm tests/test_cli_sync.py
```

**IMPACT**: Removes ~400-600 lines of code for remote data fetching.

---

### Analytics Module

**LOCATION**: `src/egregora/analytics.py`

**FILES**:
```bash
src/egregora/analytics.py
tests/test_analytics.py
```

**QUESTION**: Do you use analytics features to analyze conversation patterns/metrics?

**IF NO** → Remove analytics:
```bash
rm src/egregora/analytics.py
rm tests/test_analytics.py
```

**IMPACT**: Removes ~200-400 lines of analytics code.

---

### Media Extraction

**LOCATION**: `src/egregora/media_extractor.py`

**FILES**:
```bash
src/egregora/media_extractor.py
tests/test_media_extractor.py
tests/test_unified_processor_media_extraction.py
```

**QUESTION**: Do you need to extract and process images/media from conversations?

**IF NO** → Remove media extraction:
```bash
rm src/egregora/media_extractor.py
rm tests/test_media_extractor.py
rm tests/test_unified_processor_media_extraction.py
```

**IMPACT**: Removes ~300-500 lines of media processing code.

---

### Group Discovery

**LOCATION**: `src/egregora/`

**FILES**:
```bash
src/egregora/group_discovery.py
src/egregora/discover.py
```

**QUESTION**: Do you need automatic group discovery, or do you have a fixed set of groups?

**IF FIXED GROUPS** → Remove discovery features:
```bash
rm src/egregora/group_discovery.py
rm src/egregora/discover.py
```

**IMPACT**: Removes ~200-300 lines of discovery code.

---

### Profile System

**LOCATION**: `src/egregora/profiles/`

**FILES**:
```bash
src/egregora/profiles/__init__.py
src/egregora/profiles/profile.py
src/egregora/profiles/prompts.py
src/egregora/profiles/storage.py
src/egregora/profiles/updater.py
tests/test_profile_generation.py
tests/test_profile_updater.py
```

**QUESTION**: Do you use member profiles to personalize newsletter generation?

**IF NO** → Remove profile system:
```bash
rm -rf src/egregora/profiles/
rm tests/test_profile_generation.py
rm tests/test_profile_updater.py
```

**IMPACT**: Removes ~800-1000 lines of profile management code.

---

### Tools Directory (MkDocs Plugins)

**LOCATION**: `tools/`

**FILES**:
```bash
tools/__init__.py
tools/build_posts.py
tools/build_reports.py
tools/mkdocs_build_posts_plugin.py
tools/mkdocs_media_plugin.py
```

**QUESTION**: Are you building documentation with MkDocs and custom plugins?

**IF NO** → Remove tools directory:
```bash
rm -rf tools/
```

**IMPACT**: Removes ~400-600 lines of MkDocs plugin code.

---

### Backlog Processing Script

**LOCATION**: `scripts/process_backlog.py`

**FILES**:
```bash
scripts/process_backlog.py
tests/test_process_backlog_smoke.py
```

**QUESTION**: Is this a one-off utility you're still using?

**IF NO** → Remove backlog script:
```bash
rm scripts/process_backlog.py
rm tests/test_process_backlog_smoke.py
```

**IMPACT**: Removes ~200-300 lines of backlog processing code.

---

## 🔵 PHASE 3: Test Consolidation

### Consolidate Similar Tests

Instead of having multiple test files for similar functionality, consider merging:

**EXAMPLE**: Enrichment Tests
```bash
# Currently have:
tests/test_enrichment.py                    # Original
tests/test_enrichment_simple.py             # Simplified
tests/test_enrichment_dataframe.py          # DataFrame-specific
tests/test_enrichment_with_cache.py         # Cache-specific

# Consolidate to:
tests/test_enrichment.py                    # Merge all enrichment tests here
```

**EXAMPLE**: Privacy/Security Tests
```bash
# Currently have:
tests/test_anonymizer.py
tests/test_privacy_e2e.py
tests/test_privacy_prompt.py
tests/test_security_guards.py
tests/test_unified_processor_anonymization.py

# Consolidate to:
tests/test_privacy.py                       # Merge anonymization tests
tests/test_security.py                      # Merge security tests
```

**Benefits**:
- Fewer files to maintain
- Easier to find related tests
- Reduces test discovery overhead
- Still maintains coverage

---

## 📦 Dependency Cleanup

After removing features, update `pyproject.toml` to remove unused dependencies.

### Dependencies to Review

**If removing MCP Server**:
```toml
# Remove these if not used elsewhere:
mcp                                         # MCP protocol library
```

**If removing LlamaIndex tests**:
```toml
# Remove if test_rag_llamaindex.py is removed:
llama-index                                 # LlamaIndex framework
llama-index-core
llama-index-embeddings-*
```

**If removing media extraction**:
```toml
# Review if only used in media_extractor.py:
pillow                                      # Image processing
```

**If removing analytics**:
```toml
# Review if only used in analytics.py:
# (likely shared with other modules)
```

**Development-only dependencies** to consider removing:
```toml
[tool.uv.dev-dependencies]
codespell                                   # If removing .codespellrc
markdownlint-cli2                           # If removing .markdownlint-cli2.jsonc
pre-commit                                  # If removing .pre-commit-config.yaml
```

---

## 🔧 Safe Removal Process

### Step 1: Create Pruning Branch
```bash
# Create a new branch for safe experimentation
git checkout -b prune/reduce-codebase

# Or be more specific
git checkout -b prune/phase-1-safe-removals
```

### Step 2: Execute Phase 1 (Safe Removals)
```bash
# Run all Phase 1 removal commands
# See commands in each section above

# Example batch removal:
rm .github/workflows/claude-code-review.yml \
   .github/workflows/claude.yml \
   .github/workflows/manual-claude-review.yml \
   .github/workflows/pr-codex-review.yml

rm tests/test_rag_search_deprecated.py \
   tests/test_enrichment.py \
   tests/test_enrichment_dataframe.py \
   tests/test_enrichment_with_cache.py

# Continue with other Phase 1 removals...
```

### Step 3: Run Tests
```bash
# Verify nothing broke
uv run pytest

# Or run remaining tests individually
uv run pytest tests/test_core_pipeline.py
uv run pytest tests/test_enrichment_simple.py
uv run pytest tests/test_newsletter_simple.py
```

### Step 4: Commit Phase 1
```bash
git add -A
git commit -m "prune: Remove deprecated workflows and redundant tests (Phase 1)"
```

### Step 5: Execute Phase 2 (Feature Evaluation)
```bash
# Based on your answers to the QUESTIONS in Phase 2
# Remove features you're not using

# Example: Removing MCP server (if not using)
rm -rf src/egregora/mcp_server/
rm scripts/start_mcp_server.py
rm tests/test_mcp_server.py

git add -A
git commit -m "prune: Remove unused MCP server feature (Phase 2)"
```

### Step 6: Test Again
```bash
# Run full test suite
uv run pytest

# Verify CLI still works
uv run egregora --help
```

### Step 7: Update Dependencies
```bash
# Edit pyproject.toml to remove unused dependencies
# Then sync dependencies
uv sync

# Test again
uv run pytest
```

### Step 8: Final Commit and Merge
```bash
git add pyproject.toml uv.lock
git commit -m "prune: Remove unused dependencies"

# Merge back to main
git checkout main
git merge prune/reduce-codebase

# Or create PR for review
git push origin prune/reduce-codebase
```

---

## 🎯 Phase 2 Decision Matrix

To help decide which features to remove, answer these questions:

| Feature | Question | If YES | If NO |
|---------|----------|--------|-------|
| **MCP Server** | Do you expose Egregora to LLMs via MCP? | Keep | Remove (saves ~700 lines) |
| **Remote Sync** | Do you fetch conversations from remote sources? | Keep | Remove (saves ~500 lines) |
| **Analytics** | Do you analyze conversation patterns/metrics? | Keep | Remove (saves ~300 lines) |
| **Media Extraction** | Do you process images from chats? | Keep | Remove (saves ~400 lines) |
| **Group Discovery** | Do you auto-discover conversation groups? | Keep | Remove (saves ~250 lines) |
| **Profile System** | Do you use member profiles for newsletters? | Keep | Remove (saves ~900 lines) |
| **MkDocs Tools** | Do you build documentation with custom plugins? | Keep | Remove (saves ~500 lines) |
| **Backlog Script** | Still using backlog processing? | Keep | Remove (saves ~250 lines) |

**Total potential savings**: 3,800+ lines if removing all Phase 2 features

---

## 📊 Expected Results

### Before Pruning
```
Total Files: ~120 files
Total Lines: ~15,000-20,000 lines (estimated)
Test Files: ~30 tests
CI Workflows: 6 workflows
```

### After Aggressive Pruning (All Phases)
```
Total Files: ~62 files (48% reduction)
Total Lines: ~9,000-12,000 lines (40% reduction)
Test Files: ~15 tests (50% reduction)
CI Workflows: 1-2 workflows (75% reduction)
```

### After Conservative Pruning (Phase 1 only)
```
Total Files: ~95 files (21% reduction)
Total Lines: ~13,000-17,000 lines (15% reduction)
Test Files: ~19 tests (37% reduction)
CI Workflows: 1-2 workflows (75% reduction)
```

---

## ⚠️ Important Notes

### Before Removing Anything:
1. ✅ **Backup**: Commit all changes, or work on a branch
2. ✅ **Document**: Note what you're removing and why
3. ✅ **Test**: Run full test suite after each phase
4. ✅ **Review**: Check if removed features are imported elsewhere

### After Removal:
1. ✅ **Search imports**: `grep -r "from egregora.feature_name" src/`
2. ✅ **Check CLI**: Verify `egregora --help` works
3. ✅ **Test pipeline**: Run end-to-end with real WhatsApp data
4. ✅ **Update README**: Remove documentation for removed features

### Red Flags:
- ❌ Don't remove anything imported by `__init__.py` without checking usage
- ❌ Don't remove core pipeline components (parser, processor, generator)
- ❌ Don't remove essential tests (core_pipeline, newsletter_simple)
- ❌ Test after EACH phase, not at the end

---

## 🚀 Quick Start

### Conservative Approach (Low Risk)
Remove only Phase 1 items - no feature removal:

```bash
# Create branch
git checkout -b prune/conservative

# Remove workflows
rm .github/workflows/claude-code-review.yml \
   .github/workflows/claude.yml \
   .github/workflows/manual-claude-review.yml \
   .github/workflows/pr-codex-review.yml

# Remove deprecated tests
rm tests/test_rag_search_deprecated.py

# Remove examples
rm example_enrichment.py TESTING_PLAN.md AGENTS.md

# Test
uv run pytest

# Commit
git add -A && git commit -m "prune: Conservative cleanup (Phase 1)"
```

### Aggressive Approach (High Impact)
Remove Phase 1 + unused features:

```bash
# Create branch
git checkout -b prune/aggressive

# Execute all Phase 1 commands
# Then execute Phase 2 for unused features
# See detailed commands in sections above

# Test thoroughly
uv run pytest
uv run egregora --help

# Commit
git add -A && git commit -m "prune: Aggressive cleanup (Phases 1-2)"
```

---

## 📋 Checklist

Copy this checklist and mark items as you complete them:

### Phase 1: Safe Removals
- [ ] Remove 4 redundant GitHub workflows
- [ ] Remove GitHub scripts directory
- [ ] Remove 11 deprecated/redundant test files
- [ ] Remove test stubs directory
- [ ] Remove example files (example_enrichment.py)
- [ ] Remove documentation files (TESTING_PLAN.md, AGENTS.md)
- [ ] Remove linting configs (.codespellrc, .markdownlint-cli2.jsonc)
- [ ] Remove pre-commit config
- [ ] Remove metrics directory
- [ ] **Run tests and verify**

### Phase 2: Feature Evaluation
- [ ] Evaluate MCP Server usage → Keep or Remove
- [ ] Evaluate Remote Sync usage → Keep or Remove
- [ ] Evaluate Analytics usage → Keep or Remove
- [ ] Evaluate Media Extraction usage → Keep or Remove
- [ ] Evaluate Group Discovery usage → Keep or Remove
- [ ] Evaluate Profile System usage → Keep or Remove
- [ ] Evaluate MkDocs Tools usage → Keep or Remove
- [ ] Evaluate Backlog Script usage → Keep or Remove
- [ ] **Run tests after each removal**

### Phase 3: Consolidation
- [ ] Consolidate enrichment tests
- [ ] Consolidate privacy/security tests
- [ ] Consolidate RAG tests
- [ ] **Run tests after consolidation**

### Cleanup
- [ ] Update pyproject.toml dependencies
- [ ] Run `uv sync`
- [ ] Update README.md
- [ ] Update documentation
- [ ] Final test run: `uv run pytest`
- [ ] Test CLI: `uv run egregora --help`
- [ ] Test with real data

### Git
- [ ] All changes committed
- [ ] Branch merged to main (or PR created)
- [ ] Old branch deleted
- [ ] Celebrate! 🎉

---

## 🤔 Still Unsure?

### Start Here:
If you're unsure where to start, do **Phase 1 only** (safe removals). This gives you immediate benefits with zero risk.

### Questions to Ask Yourself:
1. "When was the last time I used this feature?"
2. "Would I notice if this was gone?"
3. "Is this critical to my workflow?"
4. "Could I recreate this easily if needed?"

### Decision Rule:
**If you haven't used it in 3+ months, remove it.** You can always restore from Git history if needed.

---

## 📚 Additional Resources

### Verify Imports Before Removing
```bash
# Check where a file is imported
grep -r "from egregora.feature_name" src/
grep -r "import feature_name" src/

# Check for string references
grep -r "feature_name" src/ tests/
```

### Find Large Files
```bash
# Find the largest files in your codebase
find src/ tests/ -type f -exec wc -l {} \; | sort -rn | head -20
```

### Git History Recovery
```bash
# If you remove something by mistake, restore it:
git checkout HEAD~1 -- path/to/file.py

# Or restore entire directory:
git checkout HEAD~1 -- src/egregora/mcp_server/
```

---

## 🎉 Success Metrics

After completing the pruning plan:

✅ **Reduced file count** by 30-50%  
✅ **Reduced lines of code** by 30-40%  
✅ **Simplified CI/CD** (1-2 workflows vs 6)  
✅ **Faster test execution** (fewer tests to run)  
✅ **Easier maintenance** (less code to understand)  
✅ **Clearer focus** (only production-critical features)

---

**Ready to prune?** Start with the conservative approach (Phase 1 only) and gradually work through Phase 2 based on your actual usage patterns.

Good luck! 🌳✂️
