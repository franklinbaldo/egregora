# Test Configuration Refactoring Plan

## Executive Summary

This PR refactors the test suite to strictly adhere to the **Fixture/Override Pattern** for test configuration, eliminating dangerous reliance on production defaults and reducing code duplication.

**Current State:** While egregora has excellent test configuration infrastructure (`test_config` fixture, proper mocking, tmp_path isolation), several tests bypass this system and directly instantiate configuration objects.

**Goal:** All tests should use centralized fixtures for configuration, with infrastructure (DBs, file paths, API keys) globally overridden for safety, and business logic values hardcoded only when testing specific behavior.

---

## Problems Identified

### Critical Issues (Must Fix)

1. **Direct `EgregoraConfig()` Instantiation (4 occurrences)**
   - `tests/e2e/pipeline/test_site_generation.py:138` - No tmp_path isolation
   - `tests/unit/rag/test_rag_backend_factory.py:43` - Uses production defaults
   - `tests/e2e/input_adapters/test_dynamic_parser.py:34,47` - Ignores test fixtures

   **Risk:** These tests may write to real `.egregora/` directories, fail in CI/CD, or have non-deterministic behavior.

2. **Direct Settings Class Instantiation (10+ occurrences)**
   - `tests/unit/rag/test_embedding_router.py:31-38` - Module-level `ModelSettings()`, `RAGSettings()`
   - `tests/unit/agents/test_rag_exception_handling.py` - 5 instances of `RAGSettings()` per test

   **Risk:** Tests depend on production model names, rate limits, and quotas instead of test-controlled values.

3. **Missing Fixtures for Common Patterns**
   - No `minimal_config` fixture for fast unit tests (RAG disabled, enrichment disabled)
   - No `test_rag_settings` or `test_model_settings` fixtures
   - No factory pattern for quick per-test customization

   **Impact:** Developers create ad-hoc configs, leading to duplication and inconsistency.

---

## Refactoring Strategy

### Phase 1: Add Missing Fixtures (Priority: HIGH)

**Goal:** Provide test-appropriate fixtures for all configuration needs.

#### 1.1 Add Settings Fixtures to `tests/conftest.py`

```python
@pytest.fixture
def test_model_settings():
    """Model settings optimized for testing.

    Uses fast test models and avoids production API limits.
    """
    settings = ModelSettings()
    settings.writer = "test-writer-model"
    settings.embedding = "test-embedding-model"
    settings.reader = "test-reader-model"
    return settings


@pytest.fixture
def test_rag_settings():
    """RAG settings for unit tests (disabled by default).

    Most unit tests don't need RAG. Enable explicitly in RAG-specific tests.
    """
    return RAGSettings(
        enabled=False,
        top_k=3,  # Smaller for tests
        min_similarity_threshold=0.7,
        embedding_max_batch_size=3,  # Faster than default 100
        embedding_timeout=5.0,  # Shorter than default 60s
    )


@pytest.fixture
def test_rag_settings_enabled(test_rag_settings):
    """RAG settings with RAG enabled (for RAG tests)."""
    settings = test_rag_settings.model_copy(deep=True)
    settings.enabled = True
    return settings


@pytest.fixture
def minimal_config(tmp_path: Path):
    """Minimal EgregoraConfig for fast unit tests.

    Use this for unit tests that don't need full pipeline infrastructure.
    Disables slow components (RAG, enrichment, reader) by default.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        EgregoraConfig with minimal settings for unit tests
    """
    config = create_default_config(site_root=tmp_path / "site")

    # Disable slow components
    config.rag.enabled = False
    config.enrichment.enabled = False
    config.reader.enabled = False

    # Use test models (fast, no API calls)
    config.models.writer = "test-model"
    config.models.embedding = "test-embedding"

    # Fast quotas for tests
    config.quota.daily_llm_requests = 10
    config.quota.per_second_limit = 10

    return config


@pytest.fixture
def config_factory(tmp_path: Path):
    """Factory for creating customized test configs.

    Use this when you need to test specific configuration values.

    Example:
        def test_custom_timeout(config_factory):
            config = config_factory(rag__enabled=True, rag__timeout=0.1)
            assert config.rag.enabled is True
            assert config.rag.timeout == 0.1

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Factory function that creates EgregoraConfig with kwargs
    """
    def _factory(**overrides):
        config = create_default_config(site_root=tmp_path / "site")

        # Apply overrides using __ syntax for nested settings
        # Example: rag__enabled=True -> config.rag.enabled = True
        for key, value in overrides.items():
            parts = key.split("__")
            obj = config
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)

        return config
    return _factory
```

**Files Changed:**
- `tests/conftest.py` (+80 lines)

**Testing:**
- Add fixture usage examples to docstrings
- Verify fixtures work in isolation (no side effects)

---

#### 1.2 Update Fixture Documentation in `tests/conftest.py`

Add header comment explaining fixture selection:

```python
# =============================================================================
# Test Configuration Fixtures - Selection Guide
# =============================================================================
#
# Use these fixtures instead of directly instantiating EgregoraConfig or Settings.
#
# RULE 1: Never use production config in tests
#   ❌ config = EgregoraConfig()  # Uses production defaults!
#   ✅ config = test_config        # Uses test defaults with tmp_path
#
# RULE 2: Pick the right fixture for your test type
#   - Unit tests (fast, no I/O):     minimal_config
#   - Integration tests (with mocks): test_config
#   - E2E tests (full pipeline):     pipeline_test_config
#   - RAG-specific tests:            rag_test_config (or test_rag_settings_enabled)
#   - Reader agent tests:            reader_test_config
#
# RULE 3: Customize with factory or model_copy()
#   - Quick customization:  config_factory(rag__enabled=True)
#   - Full control:         test_config.model_copy(deep=True)
#
# RULE 4: Never hardcode infrastructure
#   ❌ db_path = Path("/var/egregora/db.duckdb")
#   ✅ db_path = tmp_path / "test.duckdb"
#
# =============================================================================
```

**Files Changed:**
- `tests/conftest.py` (+25 lines documentation)

---

### Phase 2: Fix Direct Config Instantiations (Priority: HIGH)

**Goal:** Replace all direct `EgregoraConfig()` and `Settings()` calls with fixtures.

#### 2.1 Fix `tests/e2e/pipeline/test_site_generation.py`

**Before:**
```python
# Line 138
config = EgregoraConfig()
config.pipeline.step_size = 100
config.enrichment.enabled = False
config.rag.enabled = False
```

**After:**
```python
def test_site_generation_e2e(clean_blog_dir, monkeypatch, pipeline_test_config):
    # Use pipeline_test_config (already has enrichment/RAG disabled)
    config = pipeline_test_config.model_copy(deep=True)
    config.pipeline.step_size = 100  # Only override what's specific to this test
    # ... rest of test
```

**Files Changed:**
- `tests/e2e/pipeline/test_site_generation.py:120` (function signature)
- `tests/e2e/pipeline/test_site_generation.py:138` (config creation)

---

#### 2.2 Fix `tests/unit/rag/test_rag_backend_factory.py`

**Before:**
```python
# Line 43
config = EgregoraConfig()
config.rag.embedding_max_batch_size = 7
config.rag.embedding_timeout = 3.5
config.models.embedding = "models/test-embedding"
```

**After:**
```python
def test_embed_fn_uses_rag_settings_for_router(
    monkeypatch: pytest.MonkeyPatch,
    config_factory,  # NEW: Use factory fixture
) -> None:
    """Embedding router should be constructed with configured RAG settings."""

    # Use factory to create config with specific test values
    config = config_factory(
        rag__embedding_max_batch_size=7,
        rag__embedding_timeout=3.5,
        models__embedding="models/test-embedding",
    )

    # ... rest of test unchanged
```

**Files Changed:**
- `tests/unit/rag/test_rag_backend_factory.py:40` (function signature)
- `tests/unit/rag/test_rag_backend_factory.py:43-46` (config creation)

---

#### 2.3 Fix `tests/e2e/input_adapters/test_dynamic_parser.py`

**Before:**
```python
# Lines 34, 47
pattern = generate_dynamic_regex(sample_lines, EgregoraConfig())
```

**After:**
```python
def test_dynamic_regex_generator_success(mock_agent_run, minimal_config):
    # ... mock setup ...
    pattern = generate_dynamic_regex(sample_lines, minimal_config)
    # ... assertions ...

def test_dynamic_regex_generator_failure(mock_agent_run, minimal_config):
    # ... mock setup ...
    pattern = generate_dynamic_regex(sample_lines, minimal_config)
    # ... assertions ...
```

**Files Changed:**
- `tests/e2e/input_adapters/test_dynamic_parser.py:24` (function signature)
- `tests/e2e/input_adapters/test_dynamic_parser.py:34` (config usage)
- `tests/e2e/input_adapters/test_dynamic_parser.py:42` (function signature)
- `tests/e2e/input_adapters/test_dynamic_parser.py:47` (config usage)

---

#### 2.4 Fix `tests/unit/rag/test_embedding_router.py`

**Before (module-level):**
```python
# Lines 31-38 (PROBLEM: at module load time)
_model_settings = ModelSettings()
MODEL = _model_settings.embedding  # "models/gemini-embedding-001"

_rag_settings = RAGSettings()
DEFAULT_MAX_BATCH_SIZE = _rag_settings.embedding_max_batch_size
DEFAULT_TIMEOUT = _rag_settings.embedding_timeout

TEST_BATCH_SIZE = 3
TEST_TIMEOUT = 1.0
```

**After (fixture-based):**
```python
# Remove module-level instantiation

# Add fixture at top of file
@pytest.fixture
def embedding_router_config():
    """Config for embedding router tests."""
    settings = RAGSettings(
        embedding_max_batch_size=3,  # Small for unit tests
        embedding_timeout=1.0,         # Fast for unit tests
    )
    return settings

# Update all tests to use fixture
def test_create_embedding_router_initializes_queues(embedding_router_config):
    router = create_embedding_router(
        model="test-model",
        max_batch_size=embedding_router_config.embedding_max_batch_size,
        timeout=embedding_router_config.embedding_timeout,
    )
    # ... rest of test
```

**Files Changed:**
- `tests/unit/rag/test_embedding_router.py:31-38` (remove module-level)
- `tests/unit/rag/test_embedding_router.py` (add fixture, update ~10 test functions)

---

#### 2.5 Fix `tests/unit/agents/test_rag_exception_handling.py`

**Before (repeated 5 times):**
```python
# Lines 20, 47, 80, 95, 107
mock_resources.retrieval_config = RAGSettings()
# or
mock_resources.retrieval_config = RAGSettings(enabled=False)
```

**After:**
```python
# Add parametrized fixture
@pytest.fixture
def mock_resources_with_rag(test_rag_settings):
    """Mock WriterResources with test RAG settings."""
    return SimpleNamespace(
        retrieval_config=test_rag_settings,
        # ... other fields
    )

# Use fixture in tests
def test_rag_enabled_but_no_hits_returns_none(mock_resources_with_rag):
    mock_resources = mock_resources_with_rag
    # ... rest of test
```

**Alternatively (if different RAG states needed per test):**
```python
@pytest.fixture
def rag_settings_factory():
    """Factory for creating RAG settings with overrides."""
    def _create(enabled=True, **kwargs):
        return RAGSettings(enabled=enabled, **kwargs)
    return _create

def test_rag_enabled_but_no_hits_returns_none(rag_settings_factory):
    mock_resources = SimpleNamespace(
        retrieval_config=rag_settings_factory(enabled=True)
    )
    # ... rest of test
```

**Files Changed:**
- `tests/unit/agents/test_rag_exception_handling.py` (add fixture)
- `tests/unit/agents/test_rag_exception_handling.py` (update 5 test functions)

---

### Phase 3: Add Test Documentation (Priority: MEDIUM)

**Goal:** Document fixture usage patterns for future developers.

#### 3.1 Create `tests/README.md`

```markdown
# Egregora Test Suite

## Test Configuration Philosophy

We follow the **Fixture/Override Pattern** for test configuration:

1. **Load base configuration** - Use `create_default_config()`
2. **Override infrastructure globally** - Fixtures set tmp_path, test models, disabled slow components
3. **Hardcode specific values only in tests** - Only when testing that specific behavior

### Fixture Selection Guide

| Test Type | Fixture | Use Case |
|-----------|---------|----------|
| **Fast unit tests** | `minimal_config` | No RAG, enrichment, or reader; fast models |
| **Integration tests** | `test_config` | Full config with tmp_path isolation |
| **Pipeline E2E** | `pipeline_test_config` | Optimized for full pipeline runs |
| **RAG tests** | `test_rag_settings_enabled` | RAG enabled with test settings |
| **Reader tests** | `reader_test_config` | Reader agent enabled |
| **Custom needs** | `config_factory(key=val)` | Quick per-test customization |

### Examples

#### ✅ Good: Using fixtures
```python
def test_something(minimal_config):
    # Config is isolated, uses tmp_path, safe for unit tests
    result = do_something(minimal_config)
    assert result.status == "success"
```

#### ❌ Bad: Direct instantiation
```python
def test_something():
    config = EgregoraConfig()  # WRONG: Uses production defaults!
    result = do_something(config)
```

#### ✅ Good: Customizing via factory
```python
def test_custom_timeout(config_factory):
    config = config_factory(rag__enabled=True, rag__timeout=0.1)
    # Only the specific values needed for this test are overridden
    assert config.rag.timeout == 0.1
```

#### ✅ Good: Customizing via model_copy
```python
def test_with_custom_setting(test_config):
    config = test_config.model_copy(deep=True)
    config.pipeline.step_size = 100  # Test-specific override
    result = run_pipeline(config)
```

### Running Tests

```bash
# All tests
uv run pytest tests/

# Fast unit tests only
uv run pytest tests/unit/

# E2E tests (slower)
uv run pytest tests/e2e/

# Specific test file
uv run pytest tests/unit/rag/test_lancedb_backend.py

# With coverage
uv run pytest --cov=egregora tests/
```

### Fixtures Reference

See `tests/conftest.py` for complete fixture documentation.
```

**Files Changed:**
- `tests/README.md` (+100 lines, new file)

---

### Phase 4: Validation and Cleanup (Priority: LOW)

#### 4.1 Add Pre-commit Hook to Prevent Violations

Create `dev_tools/check_test_config.py`:

```python
#!/usr/bin/env python3
"""Pre-commit hook to prevent direct config instantiation in tests.

Checks for:
- Direct EgregoraConfig() calls without fixtures
- Direct Settings class instantiation
- Hardcoded infrastructure paths
"""

import re
import sys
from pathlib import Path

VIOLATIONS = [
    (r"EgregoraConfig\(\)", "Use test_config fixture instead of EgregoraConfig()"),
    (r"RAGSettings\(\)", "Use test_rag_settings fixture instead of RAGSettings()"),
    (r"ModelSettings\(\)", "Use test_model_settings fixture instead of ModelSettings()"),
    (r'db_path = Path\("/[^"]+"', "Use tmp_path fixture instead of hardcoded paths"),
]

def check_file(file_path: Path) -> list[str]:
    """Check a single file for violations."""
    errors = []
    content = file_path.read_text()

    for pattern, message in VIOLATIONS:
        if re.search(pattern, content):
            errors.append(f"{file_path}:{message}")

    return errors

def main():
    test_files = Path("tests").rglob("test_*.py")
    all_errors = []

    for file_path in test_files:
        # Skip conftest.py (defines fixtures)
        if file_path.name == "conftest.py":
            continue

        errors = check_file(file_path)
        all_errors.extend(errors)

    if all_errors:
        print("❌ Test configuration violations found:")
        for error in all_errors:
            print(f"  - {error}")
        print("\nSee tests/README.md for proper fixture usage.")
        return 1

    print("✅ All tests use proper configuration fixtures")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

Add to `.pre-commit-config.yaml`:

```yaml
  - repo: local
    hooks:
      - id: check-test-config
        name: Check test configuration
        entry: python dev_tools/check_test_config.py
        language: system
        pass_filenames: false
        files: tests/.*\.py$
```

**Files Changed:**
- `dev_tools/check_test_config.py` (+50 lines, new file)
- `.pre-commit-config.yaml` (+6 lines)

---

#### 4.2 Update CLAUDE.md Testing Section

Add to `CLAUDE.md` under `## Testing`:

```markdown
### Test Configuration Rules

**CRITICAL: Never use production config in tests**

1. **Use fixtures for ALL configuration:**
   - ❌ `config = EgregoraConfig()` (uses production defaults!)
   - ✅ `def test_foo(test_config):` (isolated test config)

2. **Pick the right fixture:**
   - Unit tests: `minimal_config` (fast, RAG/enrichment disabled)
   - Integration: `test_config` (full config, tmp_path)
   - E2E: `pipeline_test_config` (optimized for pipeline)
   - RAG tests: `test_rag_settings_enabled`

3. **Customize via factory or model_copy:**
   ```python
   # Factory (quick)
   config = config_factory(rag__enabled=True, rag__timeout=0.1)

   # model_copy (full control)
   config = test_config.model_copy(deep=True)
   config.pipeline.step_size = 100
   ```

4. **Infrastructure must use tmp_path:**
   - ❌ `db_path = Path(".egregora/db.duckdb")`
   - ✅ `db_path = tmp_path / "test.duckdb"`

See `tests/README.md` for complete guide.
```

**Files Changed:**
- `CLAUDE.md` (+30 lines in Testing section)

---

## Implementation Plan

### Week 1: Foundation
- [ ] **Day 1-2:** Add fixtures to `tests/conftest.py` (Phase 1.1)
- [ ] **Day 2-3:** Update fixture documentation (Phase 1.2)
- [ ] **Day 3-5:** Create `tests/README.md` (Phase 3.1)

### Week 2: Refactoring
- [ ] **Day 1:** Fix `test_site_generation.py` (Phase 2.1)
- [ ] **Day 1:** Fix `test_rag_backend_factory.py` (Phase 2.2)
- [ ] **Day 2:** Fix `test_dynamic_parser.py` (Phase 2.3)
- [ ] **Day 2-3:** Fix `test_embedding_router.py` (Phase 2.4)
- [ ] **Day 3:** Fix `test_rag_exception_handling.py` (Phase 2.5)

### Week 3: Validation
- [ ] **Day 1:** Add pre-commit hook (Phase 4.1)
- [ ] **Day 2:** Update CLAUDE.md (Phase 4.2)
- [ ] **Day 3:** Run full test suite, verify no regressions
- [ ] **Day 4:** Code review and adjustments
- [ ] **Day 5:** Final testing and merge

---

## Success Criteria

1. **Zero direct config instantiations:**
   - No `EgregoraConfig()` calls outside conftest.py
   - No `RAGSettings()`, `ModelSettings()` calls outside conftest.py

2. **All tests use fixtures:**
   - Unit tests use `minimal_config` or `config_factory`
   - E2E tests use `pipeline_test_config` or `test_config`
   - RAG tests use `test_rag_settings_enabled`

3. **Infrastructure isolation:**
   - All database paths use `tmp_path`
   - No hardcoded `.egregora/` paths
   - All API keys mocked via fixtures

4. **Documentation complete:**
   - `tests/README.md` explains fixture usage
   - `tests/conftest.py` has selection guide
   - `CLAUDE.md` updated with test config rules

5. **Pre-commit validation:**
   - Hook prevents new violations
   - Existing tests pass hook

6. **Test suite passes:**
   - All unit tests pass: `pytest tests/unit/`
   - All E2E tests pass: `pytest tests/e2e/`
   - No new warnings or errors

---

## Files Modified Summary

| File | Changes | Lines |
|------|---------|-------|
| `tests/conftest.py` | Add fixtures + docs | +105 |
| `tests/README.md` | New file | +100 |
| `tests/e2e/pipeline/test_site_generation.py` | Use fixture | -3, +2 |
| `tests/unit/rag/test_rag_backend_factory.py` | Use factory | -4, +8 |
| `tests/e2e/input_adapters/test_dynamic_parser.py` | Use fixture | -2, +4 |
| `tests/unit/rag/test_embedding_router.py` | Remove module-level | -8, +15 |
| `tests/unit/agents/test_rag_exception_handling.py` | Use fixture factory | -5, +10 |
| `dev_tools/check_test_config.py` | New file | +50 |
| `.pre-commit-config.yaml` | Add hook | +6 |
| `CLAUDE.md` | Update testing section | +30 |
| **Total** | **10 files** | **~320 lines** |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tests fail after refactoring | Medium | High | Run full test suite after each change |
| Fixtures have bugs | Low | Medium | Test fixtures in isolation first |
| Breaking existing workflows | Low | Low | Changes are internal to tests only |
| Pre-commit hook false positives | Medium | Low | Careful regex patterns, manual review |

---

## Rollback Plan

If refactoring causes issues:

1. **Immediate:** Revert to previous commit
2. **Phase-by-phase:** Each phase is independent; can roll back partial changes
3. **Fixture bugs:** Disable new fixtures, fall back to test_config
4. **Pre-commit issues:** Disable hook temporarily

---

## References

- **Industry Standard:** Fixture/Override Pattern (pytest best practices)
- **Egregora Docs:** `docs/testing/` (if exists), `CLAUDE.md` Testing section
- **Pytest Docs:** https://docs.pytest.org/en/stable/fixture.html

---

## PR Checklist

- [ ] All new fixtures have docstrings with examples
- [ ] `tests/README.md` created with usage guide
- [ ] All direct `EgregoraConfig()` calls replaced
- [ ] All direct `Settings()` calls replaced
- [ ] Pre-commit hook added and tested
- [ ] Full test suite passes (`pytest tests/`)
- [ ] No new test warnings
- [ ] CLAUDE.md updated
- [ ] Code review requested
- [ ] CI/CD pipeline passes
