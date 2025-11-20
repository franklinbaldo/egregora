# Test Configuration Refactoring Plan

**Status**: 🔴 Tech Debt
**Priority**: P1
**Effort**: ~2-4 hours
**Created**: 2025-11-20

## Problem Statement

Tests currently construct configuration objects piecemeal, leading to fragile and unrealistic test setups that don't reflect production usage patterns.

### Current Anti-Patterns

**Pattern 1: Manual Settings Construction**
```python
# tests/e2e/test_extended_e2e.py
config = ReaderSettings(
    enabled=True,
    comparisons_per_post=1,
    k_factor=32,
    database_path=".egregora/reader.duckdb",
)
```

**Pattern 2: Partial Context Construction**
```python
# tests/e2e/input_adapters/test_whatsapp_adapter.py
enrichment_context = EnrichmentRuntimeContext(
    cache=cache,
    docs_dir=docs_dir,
    posts_dir=posts_dir,
    output_format=None,  # Easy to forget required fields!
)
```

**Pattern 3: Inconsistent Config Usage**
```python
# Some tests use create_default_config()
config = create_default_config()

# Others construct manually
config = ReaderSettings(enabled=True, ...)

# Others pass raw values
process_whatsapp_export(input_path, output, ...)
```

### Why This Is Problematic

1. **Fragile**: Adding a required field breaks tests in unpredictable places
2. **Incomplete**: Tests miss required fields (we just experienced this with `output_format`)
3. **Unrealistic**: Production uses `EgregoraConfig`, tests use ad-hoc objects
4. **Hard to Maintain**: Config changes require hunting down dozens of test instantiations
5. **No Type Safety**: Missing fields only caught at runtime
6. **Difficult Debugging**: Test failures don't reflect production failures

### Impact

- ⚠️ **Recent Example**: After adding `output_format` to `EnrichmentRuntimeContext`, 2 tests failed
- ⚠️ **Maintenance Cost**: Every config change requires checking ~50+ test files
- ⚠️ **False Confidence**: Tests pass but production config might be invalid

## Solution: Centralized Test Fixtures

### Design Principles

1. **Single Source of Truth**: All tests use `EgregoraConfig` or fixtures that return it
2. **Production Parity**: Test config creation mirrors production config loading
3. **Composable**: Easy to override specific settings for test scenarios
4. **Type Safe**: Pydantic validation catches missing/invalid fields at test setup
5. **Maintainable**: Config changes automatically propagate to all tests

### Architecture

```
tests/conftest.py
├── base_config()          → Minimal valid EgregoraConfig
├── test_config()          → EgregoraConfig with test overrides
├── reader_config()        → Config with reader agent enabled
├── enrichment_config()    → Config with enrichment enabled
└── pipeline_config()      → Config for full pipeline tests

Individual test files
└── Use fixtures, override specific values as needed
```

## Implementation Plan

### Phase 1: Add Centralized Fixtures (30 min)

**File**: `tests/conftest.py`

```python
@pytest.fixture
def base_config() -> EgregoraConfig:
    """Minimal valid configuration for testing.

    Uses in-memory defaults, no external dependencies.
    """
    return create_default_config()


@pytest.fixture
def test_config(tmp_path: Path, base_config: EgregoraConfig) -> EgregoraConfig:
    """Test configuration with tmp_path overrides.

    Overrides paths to use pytest tmp_path for isolation.
    """
    config = base_config.model_copy(deep=True)

    # Override paths for test isolation
    site_root = tmp_path / "site"
    site_root.mkdir(parents=True, exist_ok=True)

    # Update all path-related settings
    # (This becomes the single place to handle path logic)

    return config


@pytest.fixture
def reader_test_config(test_config: EgregoraConfig) -> EgregoraConfig:
    """Config with reader agent enabled for testing."""
    config = test_config.model_copy(deep=True)
    config.reader.enabled = True
    config.reader.comparisons_per_post = 1  # Fast tests
    config.reader.k_factor = 32
    return config


@pytest.fixture
def enrichment_test_config(test_config: EgregoraConfig) -> EgregoraConfig:
    """Config with enrichment enabled for testing."""
    config = test_config.model_copy(deep=True)
    config.enrichment.enabled = True
    # Add enrichment-specific test overrides
    return config


@pytest.fixture
def pipeline_test_config(test_config: EgregoraConfig) -> EgregoraConfig:
    """Config for full pipeline E2E tests."""
    config = test_config.model_copy(deep=True)
    config.reader.enabled = False  # Disable slow components
    config.enrichment.enabled = False
    return config
```

### Phase 2: Refactor E2E Tests (1-2 hours)

**Priority Order:**

1. ✅ **Reader Agent Tests** (`tests/e2e/test_extended_e2e.py`)
   - Replace `ReaderSettings(...)` with `reader_test_config` fixture
   - Remove manual path construction

2. ✅ **WhatsApp Adapter Tests** (`tests/e2e/input_adapters/test_whatsapp_adapter.py`)
   - Replace `EnrichmentRuntimeContext(...)` with config-derived context
   - Use `enrichment_test_config` fixture

3. ✅ **Pipeline Tests** (`tests/e2e/pipeline/test_write_pipeline.py`)
   - Replace `WhatsAppProcessOptions(...)` with config-derived options
   - Use `pipeline_test_config` fixture

4. ✅ **CLI Tests** (`tests/e2e/cli/test_*.py`)
   - Ensure CLI tests use proper config fixtures

### Phase 3: Create Helper Functions (30 min)

**File**: `tests/helpers.py`

```python
def config_to_runtime_context(
    config: EgregoraConfig,
    tmp_path: Path,
) -> EnrichmentRuntimeContext:
    """Convert EgregoraConfig to EnrichmentRuntimeContext.

    Centralizes the logic for creating runtime contexts from config.
    Production code should also use this pattern.
    """
    cache = EnrichmentCache(tmp_path / ".cache")

    return EnrichmentRuntimeContext(
        cache=cache,
        docs_dir=config.docs_dir,  # From config
        posts_dir=config.posts_dir,  # From config
        output_format=config.output_format,  # From config
        site_root=config.site_root,
        # ... all fields derived from config
    )


def config_to_process_options(
    config: EgregoraConfig,
) -> WhatsAppProcessOptions:
    """Convert EgregoraConfig to WhatsAppProcessOptions.

    Centralizes conversion logic.
    """
    return WhatsAppProcessOptions(
        input_path=config.input_path,
        output_dir=config.output_dir,
        # ... all fields from config
    )
```

### Phase 4: Refactor Unit Tests (30 min)

**Files**: `tests/unit/**/*.py`

- Use same fixture pattern
- Add specialized fixtures as needed (e.g., `mock_api_config`)

### Phase 5: Update Documentation (15 min)

**File**: `docs/testing/e2e_strategy.md`

Add section:
```markdown
## Test Configuration

All tests MUST use `EgregoraConfig` via fixtures in `conftest.py`.

### Available Fixtures

- `base_config`: Minimal valid config
- `test_config`: Config with tmp_path overrides
- `reader_test_config`: Reader agent enabled
- `enrichment_test_config`: Enrichment enabled
- `pipeline_test_config`: Full pipeline config

### Usage Pattern

```python
def test_my_feature(reader_test_config: EgregoraConfig):
    # Override specific values if needed
    config = reader_test_config.model_copy(deep=True)
    config.reader.comparisons_per_post = 5

    # Use config
    result = run_reader_evaluation(..., config=config.reader)
```

### Anti-Patterns to Avoid

❌ Manual construction: `ReaderSettings(enabled=True, ...)`
❌ Partial contexts: `EnrichmentRuntimeContext(cache=..., docs_dir=...)`
❌ Raw parameters: Function calls with 10+ individual parameters

✅ Use fixtures: `reader_test_config`
✅ Derive contexts: `config_to_runtime_context(config)`
✅ Config-driven: Pass config objects, not individual values
```

## Validation Criteria

### Success Metrics

- [ ] All E2E tests use `EgregoraConfig` fixtures
- [ ] No manual `Settings` construction in tests
- [ ] No partial `RuntimeContext` construction in tests
- [ ] Helper functions centralize config→context conversions
- [ ] Adding a config field doesn't break tests (Pydantic catches it)
- [ ] Tests pass with same success rate as before refactoring

### Test Coverage

```bash
# Run full test suite
uv run pytest tests/

# Expected results:
# - 88+ passed
# - 29 skipped (expected)
# - 9 xfailed (known issues)
# - 0 failures ✅
```

## Benefits After Refactoring

### For Developers

- ✅ Adding config fields: Update `EgregoraConfig`, Pydantic validates everywhere
- ✅ Test setup: Import fixture, use config, done
- ✅ Debugging: Test config mirrors production config exactly

### For Codebase Health

- ✅ **Type Safety**: Pydantic catches missing/invalid config at test setup
- ✅ **Maintainability**: Single place to update test config logic
- ✅ **Realism**: Tests use the same config path as production
- ✅ **DRY**: No duplicated config construction logic

### For Onboarding

New contributors see:
```python
def test_reader_agent(reader_test_config: EgregoraConfig):
    # Clear: config comes from fixture
    result = run_reader_evaluation(config=reader_test_config.reader)
```

Not:
```python
def test_reader_agent(tmp_path):
    # Unclear: Where do these values come from? What's missing?
    config = ReaderSettings(
        enabled=True,
        comparisons_per_post=1,
        k_factor=32,
        database_path=".egregora/reader.duckdb",
        # ... did I forget anything?
    )
```

## Migration Strategy

### Incremental Approach

1. ✅ Add fixtures to `conftest.py` (non-breaking)
2. ✅ Refactor one test file at a time
3. ✅ Run tests after each file (ensure no regressions)
4. ✅ Mark old patterns with deprecation comments
5. ✅ Remove old patterns in final sweep

### Rollout Plan

**Week 1** (This sprint):
- Phase 1: Add centralized fixtures ✅
- Phase 2: Refactor E2E tests ✅
- Phase 3: Create helper functions ✅

**Week 2** (Next sprint):
- Phase 4: Refactor unit tests
- Phase 5: Update documentation

### Risk Mitigation

- **Risk**: Tests break during refactoring
  - **Mitigation**: Refactor one file at a time, run tests after each

- **Risk**: Config fixtures too rigid, can't override for edge cases
  - **Mitigation**: Use `model_copy(deep=True)` for per-test customization

- **Risk**: Increased test setup complexity
  - **Mitigation**: Document common patterns, provide helper functions

## Related Issues

- #827: E2E Testing Strategy (defines testing layers)
- #828: Reader Agent E2E Tests (highlighted `output_format` missing field issue)

## References

- `src/egregora/config/settings.py` - EgregoraConfig definition
- `tests/conftest.py` - Existing fixtures
- `docs/testing/e2e_strategy.md` - E2E testing philosophy
