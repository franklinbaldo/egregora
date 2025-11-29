# Dead Code Analysis Report
**Generated:** 2025-11-29
**Project:** Egregora v2.0.0
**Analysis Tools:** vulture, deptry, ruff, pytest-cov, radon

## Executive Summary

This report provides a comprehensive dead code analysis of the Egregora codebase, identifying:
- Unused variables and code (vulture)
- Unused dependencies (deptry)
- Untested code paths (coverage)
- Complex functions requiring refactoring (radon)

**Overall Health:** Good
- ✅ No unused imports detected (ruff)
- ⚠️ 25 unused variables found (vulture)
- ⚠️ 4 potentially unused dependencies (deptry)
- ⚠️ 34% test coverage (unit tests only)
- ⚠️ 1 function with very high complexity (D grade)

---

## 1. Unused Variables (Vulture - 100% Confidence)

### Production Code Issues (7 items)

#### src/egregora/database/duckdb_manager.py:535
**Unused exception variables:**
```python
exc_type, exc_val, exc_tb  # All unused (100% confidence)
```
**Impact:** Low - Exception handling cleanup
**Action:** Remove unused exception tuple unpacking or use them for logging

#### src/egregora/database/run_store.py:176
**Unused exception variables:**
```python
exc_type, exc_val, exc_tb  # All unused (100% confidence)
```
**Impact:** Low - Exception handling cleanup
**Action:** Remove unused exception tuple unpacking or use them for logging

#### src/egregora/output_adapters/base.py:277
**Unused variable:**
```python
posts_created  # Unused (100% confidence)
```
**Impact:** Low - Unused return value
**Action:** Either use the variable or remove it

#### src/egregora/output_adapters/mkdocs/scaffolding.py:33
**Unused variable:**
```python
node  # Unused (100% confidence)
```
**Impact:** Low - Loop variable not used
**Action:** Replace with `_` if intentionally unused

### Test Code Issues (18 items)

#### tests/conftest.py
**Unused variables:**
- Line 133: `simple` (100% confidence)
- Line 138: `simple` (100% confidence)
- Line 172: `simple` (100% confidence)

**Impact:** Low - Test fixtures
**Action:** Review if these are intended mock objects or can be removed

#### tests/e2e/cli/test_write_command.py
**Unused variables:**
- Line 315: `writer_test_agent` (100% confidence)
- Line 316: `mock_batch_client` (100% confidence)

**Impact:** Low - Mock objects in tests
**Action:** Review if mocks are necessary or remove

#### tests/e2e/input_adapters/test_whatsapp_adapter.py
**Repeated pattern:**
Multiple instances of unused `mock_dynamic_regex_fallback` variable:
- Lines: 80, 94, 105, 113, 123, 138, 153, 174, 186, 232, 261

**Impact:** Low - Repeated test setup issue
**Action:** If mock is needed for side effects, prefix with `_`. Otherwise, remove.

#### tests/e2e/test_fast_with_mock.py
**Unused variables:**
- Line 20: `mock_batch_client` (100% confidence)
- Line 36: `mock_batch_client` (100% confidence)

**Impact:** Low
**Action:** Review if mock is used for side effects

#### tests/utils/test_batch.py
**Unused variable:**
- Line 120: `mock_sleep` (100% confidence)

**Impact:** Low
**Action:** Mock used for side effects (preventing actual sleep), prefix with `_`

---

## 2. Unused Dependencies (Deptry)

### High-Priority: Truly Unused Dependencies

#### Core Dependencies (Consider Removing)

1. **`returns`** - DEP002
   - Defined in pyproject.toml but never imported
   - **Impact:** Medium - Unused dependency bloat
   - **Action:** Remove with `uv remove returns` if not needed

2. **`langchain-text-splitters`** - DEP002
   - Defined but not used in codebase
   - **Impact:** Medium
   - **Action:** Remove with `uv remove langchain-text-splitters`

3. **`langchain-core`** - DEP002
   - Defined but not used in codebase
   - **Impact:** Medium
   - **Action:** Remove with `uv remove langchain-core`

4. **`tiktoken`** - DEP002
   - Defined but not used directly in Python code
   - **Impact:** Low - May be transitive dependency used by other packages
   - **Action:** Investigate if used indirectly, otherwise remove

### Low-Priority: Documentation Dependencies (Keep)

The following are flagged as unused but are actually used by MkDocs (not imported in Python):
- `mkdocs`, `mkdocs-material` (duplicated in deps)
- `mkdocs-macros-plugin`, `mkdocs-rss-plugin` (duplicated)
- `mkdocstrings`, `mkdocs-autorefs`
- `mkdocs-static-i18n`
- `mkdocs-git-revision-date-localized-plugin`
- `mkdocs-minify-plugin`
- `pymdown-extensions`
- `codespell`

**Action:** Keep these - they're used by MkDocs configuration, not imported in Python code.

### False Positives (Ignore)

- **DEP003 warnings for `egregora`**: Self-imports within the package (expected)
- **DEP003 for transitive dependencies**: `pandas`, `numpy`, `uvicorn`, `requests` - These should either be:
  - Added as explicit dependencies if used directly (recommended)
  - Or relied upon as transitive dependencies (current state)

---

## 3. Test Coverage Analysis

### Overall Coverage: 34% (Unit Tests Only)

**Coverage breakdown by module:**

#### Excellent Coverage (>80%)
- `src/egregora/config/settings.py` - 86%
- `src/egregora/input_adapters/base.py` - 90%
- `src/egregora/input_adapters/privacy_config.py` - 88%
- `src/egregora/rag/ingestion.py` - 99%
- `src/egregora/rag/lancedb_backend.py` - 86%
- `src/egregora/rag/embedding_router.py` - 82%
- `src/egregora/utils/network.py` - 85%
- `src/egregora/output_adapters/mkdocs/paths.py` - 80%
- `src/egregora/output_adapters/mkdocs/scaffolding.py` - 79%

#### Zero Coverage (0%) - Untested Code

**CLI Modules (Expected - tested in E2E):**
- `src/egregora/cli/__init__.py` - 6 lines
- `src/egregora/cli/config.py` - 91 lines
- `src/egregora/cli/main.py` - 219 lines
- `src/egregora/cli/read.py` - 64 lines
- `src/egregora/cli/runs.py` - 116 lines

**Agent Tools (Concerning):**
- `src/egregora/agents/tools/__init__.py` - 3 lines
- `src/egregora/agents/tools/skill_injection.py` - 68 lines ⚠️
- `src/egregora/agents/tools/skill_loader.py` - 89 lines ⚠️

**Configuration (Concerning):**
- `src/egregora/config/config_validation.py` - 31 lines ⚠️
- `src/egregora/privacy/config.py` - 28 lines ⚠️

**Database:**
- `src/egregora/database/elo_store.py` - 66 lines ⚠️
- `src/egregora/database/protocols.py` - 31 lines (Protocol definitions - OK)

**Utilities:**
- `src/egregora/diagnostics.py` - 137 lines ⚠️
- `src/egregora/utils/serialization.py` - 39 lines ⚠️

**Legacy RAG:**
- `src/egregora/rag/embeddings.py` - 108 lines ⚠️ (May be deprecated - see CLAUDE.md)

**Initialization:**
- `src/egregora/init/__init__.py` - 2 lines
- `src/egregora/init/scaffolding.py` - 34 lines

#### Low Coverage (<30%) - Needs Improvement

**Pipeline Orchestration:**
- `src/egregora/orchestration/write_pipeline.py` - 18% (565 total, 465 missed) 🔴
- `src/egregora/orchestration/factory.py` - 30%

**Data Processing:**
- `src/egregora/transformations/windowing.py` - 20% 🔴
- `src/egregora/transformations/enrichment.py` - 26%

**Input Adapters:**
- `src/egregora/input_adapters/whatsapp/parsing.py` - 28% 🔴
- `src/egregora/input_adapters/whatsapp/utils.py` - 23%
- `src/egregora/input_adapters/whatsapp/dynamic.py` - 28%
- `src/egregora/input_adapters/iperon_tjro.py` - 27%

**Output Adapters:**
- `src/egregora/output_adapters/mkdocs/adapter.py` - 15% (489 total, 415 missed) 🔴

**Database:**
- `src/egregora/database/duckdb_manager.py` - 25% 🔴
- `src/egregora/database/ir_schema.py` - 24%
- `src/egregora/database/streaming/stream.py` - 19%

**Knowledge & Operations:**
- `src/egregora/knowledge/profiles.py` - 11% (295 total, 262 missed) 🔴
- `src/egregora/ops/media.py` - 14% 🔴

**Utilities:**
- `src/egregora/utils/filesystem.py` - 16%
- `src/egregora/utils/paths.py` - 25%
- `src/egregora/utils/datetime_utils.py` - 23%

**Action Items:**
1. Priority 1 (🔴): Files with >400 lines missed and <20% coverage
2. Priority 2: Agent tools, config validation, diagnostics with 0% coverage
3. Priority 3: Consider if `rag/embeddings.py` is legacy code to be removed

---

## 4. Code Complexity Analysis (Radon)

### Critical Complexity (Grade D) - Immediate Refactoring Needed

#### src/egregora/agents/enricher.py:475
```
Function: _process_media_task
Complexity: D (28) 🔴 CRITICAL
```
**Impact:** High - Very complex function, difficult to test and maintain
**Action:** Break into smaller functions:
1. Media download logic
2. Caption generation
3. Description generation
4. Error handling

### High Complexity (Grade C) - Consider Refactoring

**Functions with C-grade complexity (11-20):**

#### Agent Layer
- `src/egregora/agents/enricher.py:884` - `_extract_media_candidates` (C-18)
- `src/egregora/agents/enricher.py:816` - `_extract_url_candidates` (C-15)
- `src/egregora/agents/writer.py:638` - `_extract_intercalated_log` (C-12)
- `src/egregora/agents/writer.py:855` - `write_posts_with_pydantic_agent` (C-12)
- `src/egregora/agents/writer.py:983` - `_index_new_content_in_rag` (C-12)
- `src/egregora/agents/writer.py:368` - `build_rag_context_for_prompt` (C-11)
- `src/egregora/agents/registry.py:250` - `ToolRegistry._load_profiles` (C-17)
- `src/egregora/agents/formatting.py:141` - `_table_to_records` (C-13)
- `src/egregora/agents/formatting.py:53` - `_compute_message_id` (C-11)
- `src/egregora/agents/reader/reader_runner.py:61` - `run_reader_evaluation` (C-12)
- `src/egregora/agents/banner/gemini_provider.py:26` - `GeminiImageGenerationProvider.generate` (C-16)

#### Output Adapters
- `src/egregora/output_adapters/mkdocs/adapter.py:938` - `MkDocsAdapter._get_site_stats` (C-15)
- `src/egregora/output_adapters/mkdocs/adapter.py:976` - `MkDocsAdapter._get_profiles_data` (C-13)
- `src/egregora/output_adapters/mkdocs/adapter.py:1075` - `MkDocsAdapter._append_author_cards` (C-12)
- `src/egregora/output_adapters/mkdocs/adapter.py:623` - `MkDocsAdapter._list_from_dir` (C-11)
- `src/egregora/output_adapters/mkdocs/scaffolding.py:56` - `MkDocsSiteScaffolder.scaffold_site` (C-11)
- `src/egregora/output_adapters/conventions.py:67` - `StandardUrlConvention.canonical_url` (C-11)

#### Pipeline & Orchestration
- `src/egregora/orchestration/write_pipeline.py:1179` - `_apply_filters` (C-15)
- `src/egregora/orchestration/write_pipeline.py:768` - `_pipeline_environment` (C-11)

#### Input Adapters
- `src/egregora/input_adapters/self_reflection.py:68` - `SelfInputAdapter.parse` (C-17)
- `src/egregora/input_adapters/whatsapp/dynamic.py:22` - `generate_dynamic_regex` (C-11)
- `src/egregora/input_adapters/whatsapp/utils.py:47` - `_convert_whatsapp_media_to_markdown` (C-11)

#### Knowledge & Database
- `src/egregora/knowledge/profiles.py:343` - `apply_command_to_profile` (C-16)
- `src/egregora/knowledge/profiles.py:635` - `_extract_profile_metadata` (C-16)
- `src/egregora/knowledge/profiles.py:264` - `get_active_authors` (C-15)
- `src/egregora/knowledge/profiles.py:146` - `write_profile` (C-13)
- `src/egregora/database/ir_schema.py:348` - `_ibis_to_duckdb_type` (C-11)

#### Operations & Utilities
- `src/egregora/ops/media.py:284` - `_prepare_media_document` (C-19) ⚠️
- `src/egregora/utils/batch.py:273` - `GeminiBatchClient.embed_content` (C-20) ⚠️
- `src/egregora/utils/batch.py:191` - `GeminiBatchClient.generate_content` (C-13)
- `src/egregora/utils/batch.py:367` - `GeminiBatchClient._poll_until_done` (C-12)
- `src/egregora/rag/embedding_router.py:153` - `EndpointQueue._worker` (C-14)

#### CLI
- `src/egregora/cli/main.py:526` - `doctor` (C-18)
- `src/egregora/cli/main.py:142` - `write` (C-16)
- `src/egregora/cli/runs.py:89` - `_build_run_panel_content` (C-20) ⚠️

**Summary:**
- **1 function** with D complexity (critical) 🔴
- **38 functions** with C complexity (high)
- **3 functions** with C-20 complexity (borderline D) ⚠️

---

## 5. Recommendations

### Immediate Actions (High Priority)

1. **Fix unused variables in production code** (2-3 hours)
   - Clean up exception handling in `duckdb_manager.py:535` and `run_store.py:176`
   - Fix unused variables in `output_adapters/base.py:277` and `mkdocs/scaffolding.py:33`

2. **Refactor critical complexity function** (4-8 hours)
   - `src/egregora/agents/enricher.py:475` - `_process_media_task` (D-28)
   - Break into smaller, testable functions

3. **Remove truly unused dependencies** (30 minutes)
   ```bash
   uv remove returns langchain-text-splitters langchain-core
   # Investigate tiktoken usage before removing
   ```

4. **Fix test mock variables** (1-2 hours)
   - Prefix unused mocks with `_` or remove if unnecessary
   - Focus on `test_whatsapp_adapter.py` (11 instances)

### Medium-Term Actions (Medium Priority)

5. **Improve test coverage for critical paths** (2-3 weeks)
   - Priority targets (currently <20% coverage):
     - `orchestration/write_pipeline.py` (18% → target 60%)
     - `output_adapters/mkdocs/adapter.py` (15% → target 50%)
     - `knowledge/profiles.py` (11% → target 60%)
     - `ops/media.py` (14% → target 60%)
     - `transformations/windowing.py` (20% → target 60%)

6. **Add tests for untested modules** (1-2 weeks)
   - `agents/tools/skill_injection.py` (0% → target 70%)
   - `agents/tools/skill_loader.py` (0% → target 70%)
   - `config/config_validation.py` (0% → target 80%)
   - `database/elo_store.py` (0% → target 70%)
   - `diagnostics.py` (0% → target 60%)

7. **Refactor high-complexity functions** (2-4 weeks)
   - Functions with C-20 complexity:
     - `utils/batch.py:273` - `GeminiBatchClient.embed_content` (C-20)
     - `cli/runs.py:89` - `_build_run_panel_content` (C-20)
     - `ops/media.py:284` - `_prepare_media_document` (C-19)

### Long-Term Actions (Low Priority)

8. **Investigate legacy code** (ongoing)
   - `src/egregora/rag/embeddings.py` - 0% coverage, possibly deprecated
   - Check CLAUDE.md note about legacy RAG module removal

9. **Add explicit dependencies for transitive imports** (1 day)
   - If using `pandas`, `numpy`, `requests` directly, add as explicit dependencies
   - Prevents breakage if transitive dependencies change

10. **Improve overall test coverage** (ongoing)
    - Current: 34% (unit tests only)
    - Target: 60% (unit tests)
    - E2E tests likely cover CLI modules (verify with full test run)

---

## 6. Tooling Recommendations

### Integrate into Pre-Commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
# Dead code detection (high confidence only)
- repo: https://github.com/jendrikseipp/vulture
  rev: 'v2.14'
  hooks:
    - id: vulture
      args: [src, tests, --min-confidence=80]

# Dependency checks
- repo: https://github.com/fpgmaas/deptry
  rev: '0.24.0'
  hooks:
    - id: deptry
```

### CI/CD Integration

Add to GitHub Actions workflow:

```yaml
- name: Dead code check
  run: uv run vulture src tests --min-confidence 80

- name: Complexity check
  run: uv run radon cc src -s -n C --total-average

- name: Dependency check
  run: uv run deptry .

- name: Coverage check
  run: uv run pytest --cov=egregora --cov-fail-under=34
```

### Weekly Maintenance Script

Create `scripts/code-health.sh`:

```bash
#!/bin/bash
echo "=== Running weekly code health checks ==="

echo "\n1. Checking for dead code..."
uv run vulture src tests --min-confidence 80

echo "\n2. Checking dependencies..."
uv run deptry . 2>&1 | grep "DEP002"  # Only show unused deps

echo "\n3. Checking complexity..."
uv run radon cc src -s -n C

echo "\n4. Running coverage..."
uv run pytest --cov=egregora --cov-report=term-missing --quiet

echo "\n=== Health check complete ==="
```

---

## 7. Metrics Summary

### Current State
- **Total Lines Analyzed:** 9,276 (src only)
- **Test Coverage:** 34% (unit tests only)
- **Unused Variables:** 25 (high confidence)
- **Unused Dependencies:** 4 confirmed, 10+ false positives (docs)
- **Complex Functions (C+):** 39
- **Critical Complexity (D+):** 1
- **Unused Imports:** 0 ✅

### Target State (3-6 months)
- **Test Coverage:** 60%+ (unit tests)
- **Unused Variables:** 0
- **Unused Dependencies:** 0
- **Complex Functions (C+):** <20 (focus on breaking down D/high-C)
- **Critical Complexity (D+):** 0

### Quality Trends
- ✅ **Imports:** Clean (ruff)
- ✅ **Linting:** Strong (ruff in pre-commit)
- ⚠️ **Coverage:** Needs improvement (34%)
- ⚠️ **Complexity:** Mostly acceptable, 1 critical issue
- ⚠️ **Dependencies:** Some cleanup needed

---

## Appendix A: Tool Versions

```
vulture==2.14
deptry==0.24.0
radon==6.0.1
ruff==0.14.0
pytest==8.4.2
pytest-cov==7.0.0
```

## Appendix B: False Positives & Whitelisting

### Expected Unused Variables

If you want to suppress vulture warnings for known false positives, create `vulture_whitelist.py`:

```python
# Vulture whitelist for Egregora
# False positives that should not be flagged

# Pydantic model fields (used by framework)
# Add as needed...

# Test fixtures (used by pytest)
# Add as needed...

# Exception variables used for logging (if kept)
exc_type
exc_val
exc_tb
```

Run with: `uv run vulture src tests vulture_whitelist.py --min-confidence 80`

### Deptry Configuration

Add to `pyproject.toml` to suppress false positives:

```toml
[tool.deptry]
# MkDocs dependencies are used in config, not imported
ignore_obsolete = [
    "mkdocs",
    "mkdocs-material",
    "mkdocs-macros-plugin",
    "mkdocs-rss-plugin",
    "mkdocstrings",
    "mkdocs-autorefs",
    "mkdocs-static-i18n",
    "mkdocs-git-revision-date-localized-plugin",
    "mkdocs-minify-plugin",
    "pymdown-extensions",
    "codespell",
]

# Egregora is the current package
ignore_transitive = ["egregora"]
```

---

## Appendix C: Next Steps Checklist

- [ ] Fix unused variables in production code (2-3 hours)
- [ ] Refactor `_process_media_task` function (D-28 complexity)
- [ ] Remove unused dependencies (returns, langchain-*)
- [ ] Fix test mock variables (prefix with _ or remove)
- [ ] Add tests for 0% coverage modules (skill_injection, skill_loader, etc.)
- [ ] Improve coverage for critical paths (<20% → 60%)
- [ ] Refactor C-20 complexity functions
- [ ] Integrate vulture and deptry into pre-commit hooks
- [ ] Add CI/CD checks for code health
- [ ] Create weekly maintenance script
- [ ] Set up coverage tracking (track 34% → 60% progress)

---

**Report End**
