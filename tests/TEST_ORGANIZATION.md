"""Test Organization Guide

This document explains the test structure and organization rationale for the Egregora project.

## Current Structure (Phase 4 - 2025-01-09)

The test suite is organized by test type rather than mirroring the source structure:

```
tests/
├── unit/              # Fast, isolated tests (no external dependencies)
├── integration/       # Tests with DuckDB, RAG, enrichment APIs
├── e2e/              # Full pipeline tests with golden fixtures
├── agents/           # Pydantic AI agent-specific tests
├── linting/          # Code quality checks (imports, style)
├── evals/            # LLM output quality evaluation
├── fixtures/         # Shared test fixtures and golden files
└── cassettes/        # VCR HTTP recordings for API replay
```

### Statistics

- **648 total tests** across 55 test files
- **470 unit tests** (73% of suite)
- **127 integration/e2e tests** (20% of suite)
- **42 agent tests** (6% of suite)
- **9 linting tests** (1% of suite)

## Rationale for Current Organization

### Why Not Mirror Source Structure?

**Decision:** Keep test organization by type, not by source module.

**Reasons:**

1. **Test categorization matters more than source location**
   - Developers want to run fast tests (unit) vs slow tests (integration)
   - CI pipelines need clear separation for different stages
   - `pytest tests/unit` vs `pytest tests/integration` is intuitive

2. **Many tests span multiple source modules**
   - E2E tests touch ingestion + privacy + enrichment + generation
   - Integration tests combine database + agents + utilities
   - Adapter tests cover sources + ingestion + pipeline

3. **Agent tests are a natural category**
   - All Pydantic AI agent tests share similar patterns
   - Grouped by agent type (writer, editor, ranking) not source location
   - Makes sense as a top-level category

4. **Fixtures and cassettes benefit from centralization**
   - `fixtures/golden/` used across unit/integration/e2e
   - `cassettes/` (VCR recordings) used by multiple test categories
   - Sharing is easier with flat structure

### Test Naming Conventions

**Unit tests:** `test_<module>.py` or `test_<module>_<feature>.py`
- Examples: `test_anonymizer.py`, `test_pipeline_ir.py`, `test_schema.py`

**Integration tests:** `test_<system>_<integration>.py`
- Examples: `test_duckdb_sql_integrations.py`, `test_rag_store.py`

**E2E tests:** `test_<scenario>_<variant>.py`
- Examples: `test_week1_golden.py`, `test_fast_with_mock.py`

**Agent tests:** `test_<agent>_<aspect>.py`
- Examples: `test_writer_pydantic_agent.py`, `test_writer_journal.py`

### Coverage by Domain

| Domain | Unit | Integration | E2E | Total |
|--------|------|-------------|-----|-------|
| **Pipeline** | 80 | 12 | 24 | 116 |
| **Database** | 45 | 18 | 6 | 69 |
| **Agents** | 15 | 8 | 15 | 38 |
| **Privacy** | 30 | 0 | 8 | 38 |
| **Sources/Adapters** | 85 | 4 | 0 | 89 |
| **Enrichment** | 40 | 22 | 1 | 63 |
| **Utils** | 95 | 5 | 0 | 100 |
| **Config** | 35 | 0 | 0 | 35 |
| **Other** | 45 | 4 | 0 | 49 |

## Test Quality Standards

### All Tests Must Have:
- ✅ Clear docstrings explaining what is tested
- ✅ At least one assertion (no no-op tests)
- ✅ Proper cleanup (fixtures, temp files)
- ✅ Meaningful names (not `test_1`, `test_2`)

### Integration Tests Must:
- ✅ Use VCR cassettes for API calls (deterministic, no key needed)
- ✅ Clean up DuckDB connections
- ✅ Be runnable in CI without external services

### E2E Tests Must:
- ✅ Use golden fixtures for comparison
- ✅ Test realistic user workflows
- ✅ Complete in <5 min

## Known Intentional Duplicates

Some test names appear in multiple files **intentionally**:

1. **`test_decorator_preserves_function_metadata`** (3 files)
   - Each tests a different decorator with the same pattern
   - Acceptable duplication for clarity

2. **`test_adapter_meta_structure`** (2 files)
   - Tests different adapter types (InputSource vs InputAdapter)
   - Different protocols, not duplicate tests

3. **Registry tests** (2 files each)
   - Different registry types (view registry vs adapter registry)
   - Testing same pattern across different implementations

## Future Improvements (Low Priority)

1. **Consider pytest-parametrize for similar tests**
   - Could reduce duplicate test names
   - Trade-off: harder to debug individual failures

2. **Add test coverage metrics**
   - Track coverage by domain
   - Identify untested code paths

3. **Automate golden fixture updates**
   - Currently manual (delete + re-run)
   - Could add `--update-golden` flag

## Related Documentation

- `CONTRIBUTING.md` - How to write tests
- `docs/testing-strategy.md` - Detailed testing philosophy (if exists)
- `tests/fixtures/README.md` - Golden fixture guide (if exists)
