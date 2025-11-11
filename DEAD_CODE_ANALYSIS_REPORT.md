# Dead Code Analysis Report
**Generated:** 2025-11-11
**Project:** Egregora v2.0.0
**Analysis Tools:** vulture, ruff, pytest-cov, radon, bandit

---

## Executive Summary

This comprehensive dead code analysis identified **multiple opportunities for code cleanup and improvement** across the Egregora codebase:

- **6 high-confidence dead code issues** (vulture)
- **10 unused imports/variables** (ruff)
- **38% test coverage** with 10 files at 0% coverage
- **2 extremely complex functions** (F grade) requiring refactoring
- **42 security issues** (31 medium, 11 low severity)

**Priority actions:**
1. Remove 42 lines of unreachable Slack adapter code
2. Fix unused variables in rendering and test code
3. Address 2 extremely complex functions (pipeline runner, enrichment)
4. Improve test coverage for CLI and pipeline modules (currently 0%)
5. Review SQL injection warnings in RAG and annotation stores

---

## 1. Dead Code Detection (Vulture)

### High Confidence Issues (80-100%)

#### 🔴 CRITICAL: Unreachable Code in Slack Adapter
**File:** `src/egregora/sources/slack/adapter.py:105`
**Severity:** HIGH
**Confidence:** 100%
**Lines:** 42 lines of dead code

**Issue:** Template/reference implementation code located after `raise NotImplementedError` at line 101. This code is never executed.

**Recommendation:**
- **Option A (preferred):** Delete lines 105-146 entirely since Slack support is not implemented
- **Option B:** If keeping as reference, move to a separate documentation file or comment it as a design doc
- **Rationale:** Commented-out code in production is a maintenance burden and creates confusion

```python
# Current (line 101-146):
raise NotImplementedError(msg)

# The code below is template/reference implementation  # <-- 42 lines of dead code here
# Uncomment and complete when implementing Slack support
"""
if not self.supports_format(source_path):
    ...  # 42 lines never executed
"""
```

---

#### 🟡 Unused Variables in Rendering

**File:** `src/egregora/rendering/base.py:517`
**Variable:** `window_data`
**Confidence:** 100%

**Issue:** Parameter `window_data` in `prepare_window()` method is declared but never used in the function body.

**Recommendation:**
- If truly unused, remove the parameter or prefix with underscore: `_window_data`
- If used by subclasses, add a comment explaining the Template Method pattern
- Verify whether MkDocs/Hugo subclasses actually use this parameter

```python
def prepare_window(
    self, window_label: str, window_data: dict[str, Any] | None = None  # ← unused
) -> dict[str, Any] | None:
    """Pre-processing hook called before writer agent processes a window."""
    # TODO: Check if subclasses use window_data
```

---

**File:** `src/egregora/rendering/base.py:553-554`
**Variables:** `posts_created`, `profiles_updated`
**Confidence:** 100%

**Issue:** Variables extracted from writer results but never used.

**Recommendation:**
- If these are for logging/metrics, add logging statements
- If truly unused, remove the variable assignments
- Consider using structured logging to track these metrics

```python
# Current:
posts_created = writer_results.get("posts_created", 0)  # ← unused
profiles_updated = writer_results.get("profiles_updated", 0)  # ← unused

# Suggested fix:
logger.info(
    "Window processing complete",
    posts_created=writer_results.get("posts_created", 0),
    profiles_updated=writer_results.get("profiles_updated", 0),
)
```

---

#### 🟡 Unused Test Variable

**File:** `tests/agents/test_ranking_pydantic_agent.py:81`
**Variable:** `test_posts`
**Confidence:** 100%

**Recommendation:** Remove the unused variable or add assertion using it.

---

#### 🟡 Unused Import in Tests

**File:** `tests/unit/test_telemetry.py:20`
**Import:** `opentelemetry`
**Confidence:** 90%

**Recommendation:** Remove if truly unused, or add a test that uses it.

---

## 2. Unused Imports and Variables (Ruff)

### F401: Unused Imports

1. **`src/egregora/agents/ranking/__init__.py:12`**
   - Import: `run_comparison_with_pydantic_agent`
   - **Action:** Add to `__all__` or remove if not part of public API

2. **`src/egregora/config/__init__.py:121,124,127`**
   - Imports: `EnrichmentConfig`, `PipelineConfig`, `WriterConfig`
   - **Action:** Add to `__all__` for re-export or remove

3. **`src/egregora/pipeline/__init__.py:76-78`**
   - Imports: `sys`, `module_from_spec`, `spec_from_file_location`, `Path`
   - **Action:** Remove dead code or explain why imports are needed

### F841: Unused Local Variables

1. **`tests/e2e/test_week1_golden.py:124`**
   - Variable: `actual_type`
   - **Action:** Use in assertion or remove

2. **`tests/e2e/test_week1_golden.py:183`**
   - Variable: `unique_authors_anon`
   - **Action:** Use in assertion or remove

---

## 3. Test Coverage Analysis

### Overall Coverage: **38%**

**Critical finding:** Large portions of the codebase are untested, indicating potential dead code or lack of quality assurance.

### Files with 0% Coverage (Highest Priority)

| File | Lines | Priority | Notes |
|------|-------|----------|-------|
| **`src/egregora/cli.py`** | 961 | 🔴 CRITICAL | Main CLI entry point - should have integration tests |
| **`src/egregora/pipeline/runner.py`** | 275 | 🔴 CRITICAL | Core pipeline orchestration - needs e2e tests |
| **`src/egregora/pipeline/windowing.py`** | 156 | 🔴 HIGH | Windowing logic - critical for correctness |
| **`src/egregora/enrichment/avatar_pipeline.py`** | 120 | 🟡 MEDIUM | Avatar processing - may be unused feature |
| **`src/egregora/rendering/mkdocs_documents.py`** | 224 | 🟡 MEDIUM | Document rendering - needs tests |
| **`src/egregora/pipeline/stages/filtering.py`** | 65 | 🟡 MEDIUM | Filtering stage - may be unused |
| **`src/egregora/utils/serialization.py`** | 79 | 🟡 MEDIUM | May be dead code - verify usage |
| **`src/egregora/utils/logging_setup.py`** | 35 | 🟢 LOW | Utility code |
| **`src/egregora/models.py`** | 28 | 🟢 LOW | Data models |
| **`src/egregora/pipeline/stages/__init__.py`** | 13 | 🟢 LOW | Init file |

### Files with Very Low Coverage (<20%)

| File | Coverage | Lines Untested | Priority |
|------|----------|----------------|----------|
| **`agents/shared/rag/retriever.py`** | 11% | 226/255 | 🔴 HIGH |
| **`agents/writer/formatting.py`** | 15% | 151/178 | 🔴 HIGH |
| **`enrichment/simple_runner.py`** | 13% | 166/190 | 🔴 HIGH |
| **`agents/shared/rag/embedder.py`** | 17% | 105/126 | 🟡 MEDIUM |
| **`agents/writer/core.py`** | 18% | 191/232 | 🟡 MEDIUM |
| **`agents/ranking/elo.py`** | 18% | 51/62 | 🟡 MEDIUM |
| **`agents/shared/profiler.py`** | 19% | 236/292 | 🟡 MEDIUM |
| **`enrichment/media.py`** | 17% | 101/122 | 🟡 MEDIUM |

**Recommendation:** Prioritize testing for:
1. **CLI commands** - Add integration tests for `write`, `edit`, `rank` commands
2. **Pipeline runner** - Add e2e tests for full pipeline execution
3. **RAG retriever** - Critical for content generation quality
4. **Enrichment pipeline** - Verify URL/media enrichment works correctly

---

## 4. Code Complexity Analysis (Radon)

### Overall Complexity: **A (3.37)** ✅
*Average complexity is healthy, but several outlier functions need attention*

### 🔴 F Grade: Extremely High Complexity (41+) - REWRITE URGENTLY

#### 1. `pipeline/runner.py:run_source_pipeline` - **F (50)**
**Issue:** 50 independent code paths make this function extremely difficult to test and maintain.

**Recommendation:**
- Break into smaller functions: `_setup_pipeline()`, `_process_windows()`, `_handle_enrichment()`, `_run_writer_agent()`
- Use Strategy pattern for different pipeline stages
- Extract window processing into separate class
- Target complexity: Bring down to C (11-20) or lower

**Current structure:**
```python
def run_source_pipeline(...):  # 50 cyclomatic complexity
    # Setup (10 lines)
    # Validation (20 lines)
    # Window processing loop (50 lines)
    # Enrichment logic (30 lines)
    # Writer agent invocation (40 lines)
    # Cleanup (20 lines)
    # Total: ~170 lines, 50 branches
```

**Suggested refactoring:**
```python
class SourcePipeline:
    def run(self) -> PipelineResult:
        self._setup()
        self._validate()
        for window in self._create_windows():
            self._process_window(window)
        return self._finalize()

    def _process_window(self, window):  # ← Much smaller complexity
        data = self._enrich(window)
        self._write_posts(data)
```

---

#### 2. `enrichment/simple_runner.py:enrich_table_simple` - **F (45)**
**Issue:** Complex enrichment logic with many conditional branches.

**Recommendation:**
- Extract URL enrichment into separate function
- Extract media enrichment into separate function
- Use Command pattern for different enrichment types
- Consider async/batch processing refactoring
- Target complexity: Bring down to B (6-10) or lower

---

### 🟡 D Grade: Very High Complexity (21-30) - REFACTOR SOON

| Function | File | Complexity | Action |
|----------|------|------------|--------|
| **`_extract_tool_results`** | `agents/writer/agent.py:418` | 30 | Extract parsing logic into smaller functions |
| **`write_posts_with_pydantic_agent`** | `agents/writer/agent.py:636` | 28 | Break into setup, execution, and cleanup phases |
| **`VectorStore.search`** | `agents/shared/rag/store.py:501` | 28 | Separate exact vs ANN search modes into different methods |
| **`runs_show`** | `cli.py:1852` | 25 | Extract display logic into formatter class |

---

### 🟠 C Grade: High Complexity (11-20) - CONSIDER REFACTORING

18 additional functions with C-grade complexity. While not urgent, these should be monitored and refactored opportunistically:

**Top candidates for refactoring:**
- `agents/writer/core.py:_write_posts_for_window_pydantic` (17)
- `agents/writer/formatting.py:_table_to_records` (17)
- `agents/shared/profiler.py:apply_command_to_profile` (16)
- `utils/batch.py:GeminiBatchClient.embed_content` (19)

---

## 5. Security Issues (Bandit)

### Summary
- **Total issues:** 42
- **Medium severity:** 31
- **Low severity:** 11

### 🔴 HIGH PRIORITY: SQL Injection Risks (B608)

**Count:** 29 occurrences
**Files affected:**
- `agents/shared/annotations/__init__.py` (5 occurrences)
- `agents/shared/rag/store.py` (16 occurrences)
- `database/views.py` (4 occurrences)
- `enrichment/simple_runner.py` (2 occurrences)
- Other files (2 occurrences)

**Issue:** String-based SQL query construction with f-strings.

**Example from `agents/shared/rag/store.py:143`:**
```python
self.conn.execute(
    f"CREATE OR REPLACE TABLE {TABLE_NAME} AS SELECT * FROM read_parquet(?)",
    [str(self.parquet_path)]
)
```

**Risk Assessment:**
- **Current risk:** LOW-MEDIUM
- **Reason:** `TABLE_NAME` is a constant, not user input
- **However:** This pattern is fragile and could become vulnerable if refactored

**Recommendation:**
1. **Short-term:** Add `# noqa: B608` comments with justification for each occurrence
2. **Medium-term:** Use parameterized queries where possible
3. **Long-term:** Consider using SQLAlchemy or Ibis for dynamic SQL generation
4. **Best practice:** Never interpolate user input directly into SQL strings

**Example fix:**
```python
# Before:
self.conn.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = ?", [user_id])

# After (if TABLE_NAME is truly constant):
TABLE_NAME = "rag_chunks"  # Validate this is a constant
self.conn.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = ?", [user_id])  # noqa: B608 - TABLE_NAME is constant

# Or use Ibis to avoid raw SQL:
table = ibis.table(TABLE_NAME)
result = table.filter(table.id == user_id).execute()
```

---

### 🟡 MEDIUM PRIORITY: Unsafe YAML Loading (B506)

**Count:** 2 occurrences
**Files:** `config/site.py:127`, `init/scaffolding.py:42`

**Issue:** Using `yaml.load()` instead of `yaml.safe_load()`.

**Current code:**
```python
config = yaml.load(
    mkdocs_path.read_text(encoding="utf-8"),
    Loader=_ConfigLoader
)  # noqa: S506 - trusted config file
```

**Risk Assessment:**
- **Current risk:** LOW (files are local, trusted)
- **Potential risk:** If config files become user-provided, this allows arbitrary code execution

**Recommendation:**
1. The `# noqa: S506` comments are already present, indicating awareness
2. Document why `yaml.load` is needed instead of `yaml.safe_load`
3. If possible, switch to `yaml.safe_load()` unless advanced YAML features are required
4. Add input validation if config files ever become user-provided

---

### 🟢 LOW PRIORITY: Pickle Usage (B301)

**Count:** 1 occurrence
**File:** `pipeline/legacy/checkpoint.py:191`

**Issue:** Using `pickle.load()` on checkpoint files.

**Code:**
```python
with path.open("rb") as f:
    return pickle.load(f)  # B301: Pickle security warning
```

**Risk Assessment:**
- **Current risk:** LOW (checkpoints are local files, not user-provided)
- **Note:** File is in `legacy/` module, likely deprecated

**Recommendation:**
1. Check if `pipeline/legacy/checkpoint.py` is still used (CLAUDE.md mentions using `tracking.py` instead)
2. If legacy, add deprecation warning and plan removal
3. If still used, switch to JSON or msgpack for new checkpoints
4. Add `# noqa: B301` with justification if keeping pickle

---

## 6. Dependency Analysis (deptry)

**Note:** deptry reported 313 issues, but most are **false positives**:

### False Positives (Ignore)
- **Internal imports:** All `'egregora' imported but it is a transitive dependency` warnings are incorrect (first-party package)
- **Dev tools:** pytest, ruff, mkdocs, pre-commit, etc. are dev dependencies (not imported in source code)
- **Tool plugins:** mkdocs plugins, pytest plugins (loaded via plugin systems, not direct imports)

### Potential Real Issues (Review)
1. **`.claude/skills/jules-api/jules_client.py:14`**
   - `requests` imported but it is a transitive dependency
   - **Action:** Add `requests` to skill dependencies if needed

2. **`.claude/skills/pydantic-ai-ecosystem/example_fasta2a.py:39`**
   - `uvicorn` imported but not declared
   - **Action:** These are example files, may not need fixing

3. **`.claude/skills/pydantic-ai-ecosystem/example_graph.py:7`**
   - `pydantic_graph` imported but not declared
   - **Action:** Example file, document dependency requirement

**Overall assessment:** Dependency hygiene is good. The few real issues are in example/skill code, not production code.

---

## 7. Recommendations by Priority

### 🔴 CRITICAL (Do Immediately)

1. **Remove unreachable Slack code** (42 lines in `sources/slack/adapter.py:105-146`)
   - Effort: 5 minutes
   - Impact: Reduces confusion, improves maintainability

2. **Refactor `run_source_pipeline()`** (complexity 50 → target <20)
   - Effort: 4-6 hours
   - Impact: Dramatically improves testability and maintainability
   - Blockers: None

3. **Refactor `enrich_table_simple()`** (complexity 45 → target <15)
   - Effort: 3-4 hours
   - Impact: Makes enrichment logic more testable

4. **Add tests for CLI** (currently 0% coverage)
   - Effort: 8-12 hours
   - Impact: Ensures CLI commands work correctly, catches regressions

### 🟡 HIGH (Do This Sprint)

1. **Fix all unused variables/imports** (10 ruff issues)
   - Effort: 30 minutes
   - Impact: Cleaner code, fewer false positives in future scans

2. **Add tests for pipeline runner** (0% coverage)
   - Effort: 6-8 hours
   - Impact: Critical component should have test coverage

3. **Refactor D-grade complexity functions** (4 functions)
   - Effort: 2-4 hours each
   - Impact: Improved testability

4. **Review SQL injection warnings** (29 occurrences)
   - Effort: 2-3 hours
   - Impact: Add noqa comments with justifications, identify any real risks

### 🟢 MEDIUM (Do This Month)

1. **Improve coverage for RAG components** (11-19% coverage)
   - Effort: 8-12 hours
   - Impact: Better confidence in vector search correctness

2. **Add tests for enrichment pipeline** (13% coverage)
   - Effort: 6-8 hours
   - Impact: Ensures URL/media enrichment works correctly

3. **Verify unused modules** (check if truly dead):
   - `utils/serialization.py` (0% coverage)
   - `enrichment/avatar_pipeline.py` (0% coverage)
   - `pipeline/stages/filtering.py` (0% coverage)
   - Effort: 1-2 hours investigation
   - Impact: Remove dead code or add tests

4. **Refactor C-grade complexity functions** (18 functions)
   - Effort: 1-2 hours each
   - Impact: Incremental maintainability improvements

### 🔵 LOW (Backlog)

1. **Add type hints to increase mypy coverage**
2. **Document why YAML unsafe load is necessary** (or switch to safe_load)
3. **Deprecate and remove legacy checkpoint module** (uses pickle)
4. **Set up automated dead code detection in CI** (vulture pre-commit hook)

---

## 8. Automated Cleanup Commands

### Quick Wins (Run These Now)

```bash
# 1. Fix all auto-fixable linting issues
uv run ruff check . --fix

# 2. Format all code
uv run ruff format .

# 3. Generate coverage HTML report for detailed review
uv run pytest tests/unit/ --cov=src/egregora --cov-report=html
open htmlcov/index.html  # View in browser

# 4. List all files with 0% coverage
uv run pytest tests/unit/ --cov=src/egregora --cov-report=term-missing | grep "0%"
```

### CI/CD Integration

Add to `.github/workflows/code-quality.yml`:

```yaml
- name: Dead code check
  run: uv run vulture src tests --min-confidence 80

- name: Complexity check
  run: uv run radon cc src -s -n C --total-average

- name: Coverage check
  run: uv run pytest --cov=src/egregora --cov-fail-under=40  # Start at 40%, increase gradually

- name: Security scan
  run: uv run bandit -r src --severity-level medium
```

---

## 9. Follow-Up Actions

### Immediate Next Steps

1. **Create issues for critical items:**
   - Issue #1: Refactor `run_source_pipeline()` (complexity 50)
   - Issue #2: Refactor `enrich_table_simple()` (complexity 45)
   - Issue #3: Add CLI integration tests (0% coverage)
   - Issue #4: Remove unreachable Slack adapter code

2. **Schedule refactoring sprints:**
   - Week 1: Remove dead code + fix unused imports
   - Week 2: Refactor top 2 complex functions
   - Week 3: Add CLI tests
   - Week 4: Add pipeline runner tests

3. **Monitor progress:**
   - Run this analysis monthly
   - Track coverage improvement (target: 60% by Q2)
   - Track complexity improvement (eliminate all F/D grades)

### Long-Term Goals

- **Coverage target:** 80% overall (currently 38%)
- **Complexity target:** No functions above C grade
- **Security target:** Zero medium+ severity issues
- **Dead code target:** Zero unreachable code, all imports used

---

## 10. Tool Configuration

### Recommended Pre-Commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  # Dead code detection
  - repo: https://github.com/jendrikseipp/vulture
    rev: 'v2.14'
    hooks:
      - id: vulture
        args: [src, tests, --min-confidence=80]

  # Complexity enforcement
  - repo: local
    hooks:
      - id: radon-complexity
        name: Check code complexity
        entry: uv run radon cc src -s -n C
        language: system
        pass_filenames: false
```

### Weekly Maintenance Script

Create `dev_tools/code_health_check.sh`:

```bash
#!/bin/bash
set -e

echo "🔍 Running weekly code health check..."

echo "\n📊 Coverage Report:"
uv run pytest --cov=src/egregora --cov-report=term-missing | tail -20

echo "\n🧹 Dead Code Detection:"
uv run vulture src tests --min-confidence 80

echo "\n🔢 Complexity Analysis:"
uv run radon cc src -s -n C --total-average

echo "\n🔒 Security Scan:"
uv run bandit -r src --severity-level medium -q

echo "\n✅ Code health check complete!"
```

---

## Appendix: Tool Versions

- vulture: 2.14
- ruff: (from project)
- pytest: (from project)
- pytest-cov: 7.0.0
- coverage: 7.11.3
- radon: 6.0.1
- bandit: 1.8.6
- deptry: 0.24.0

**Generated by:** Claude Code (Anthropic)
**Analysis duration:** ~5 minutes
**Total codebase size:** 22,663 lines of Python code
