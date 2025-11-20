# End-to-End (E2E) Testing Strategy & Refactoring Plan

This document outlines both the target strategy for End-to-End testing of the Egregora pipeline and a concrete plan to refactor our current testing infrastructure to match this vision.

## Table of Contents

1. [Philosophy](#philosophy)
2. [Current State Assessment](#current-state-assessment)
3. [Gap Analysis](#gap-analysis)
4. [Target Architecture](#target-architecture)
5. [Refactoring Plan](#refactoring-plan)
6. [Migration Strategy](#migration-strategy)
7. [Success Criteria](#success-criteria)
8. [Implementation Guidelines](#implementation-guidelines)

---

## Philosophy

Unlike unit tests which verify isolated functions, E2E tests validate the integration of subsystems—from raw file ingestion to final site generation—while mocking expensive external dependencies (LLMs).

### Core Principles

1. **Real I/O, Mocked Intelligence**: Use real files (ZIPs, Parquet, DuckDB) and real file system operations. Only mock the stochastic/expensive parts (Google Gemini API and PydanticAI Agent decisions).
2. **Schema as Contract**: Every test stage must verify adherence to the `IR_MESSAGE_SCHEMA` (Interchange Representation).
3. **State Verification**: Verify side effects (database rows, checkpoints, file creation) rather than just return values.
4. **Deterministic Execution**: All E2E tests must be deterministic and fast (no actual API calls in CI).
5. **Clear Boundaries**: Tests should be organized by system boundaries (Input → Pipeline → Output).

---

## Current State Assessment

### Test Structure (as of 2025-11-19)

```
tests/
├── e2e/                              # 9 test files - mixed concerns
│   ├── test_whatsapp_real_scenario.py   # ✅ Comprehensive parser + pipeline tests
│   ├── test_with_golden_fixtures.py     # ❌ XFAIL - needs pydantic-ai refactor
│   ├── test_cli_write.py                # ✅ CLI integration tests
│   ├── test_cli_runs.py                 # ✅ Observability tests
│   ├── test_cli_utilities.py            # ✅ CLI utility tests
│   ├── test_fast_with_mock.py           # ✅ Mock infrastructure validation
│   ├── test_init_template_structure.py  # ✅ Site initialization tests
│   ├── test_stage_commands.py           # ⚠️  Legacy stage tests
│   └── test_week1_golden.py             # ⚠️  Temporal test (week 1 specific)
├── integration/                      # 7 test files - infrastructure focused
│   ├── test_rag_error_handling.py
│   ├── test_rag_store.py
│   ├── test_enrichment_avatars.py
│   ├── test_enrich_table_duckdb.py
│   ├── test_annotations_store.py
│   └── test_duckdb_sql_integrations.py
├── unit/                             # 2 test files - minimal coverage
│   ├── test_writer_formatting.py
│   └── test_run_store.py
├── fixtures/
│   ├── Conversa do WhatsApp com Teste.zip
│   └── golden/expected_output/
├── cassettes/                        # VCR recordings
└── utils/
    └── mock_batch_client.py          # Mock infrastructure
```

### What's Working Well

✅ **Comprehensive WhatsApp Testing**: `test_whatsapp_real_scenario.py` provides excellent coverage of the input adapter layer
✅ **Mock Infrastructure**: Solid mocking utilities in `tests/utils/mock_batch_client.py`
✅ **VCR Integration**: Cassette-based API replay works well for integration tests
✅ **CLI Testing**: Good coverage of CLI commands and options
✅ **Observability**: Run tracking tests validate the tracking infrastructure

### What Needs Improvement

❌ **Broken Golden Fixtures**: `test_with_golden_fixtures.py` is marked as `xfail` due to pydantic-ai migration
⚠️  **Unclear Boundaries**: E2E tests mix concerns (parser + pipeline + CLI)
⚠️  **Inconsistent Mocking**: Multiple mocking strategies (monkeypatch, VCR, TestModel) without clear guidelines
⚠️  **Missing Output Adapter E2E**: No dedicated tests for MkDocs/Eleventy output generation
⚠️  **Temporal Tests**: Tests like `test_week1_golden.py` are time-bound and unclear
⚠️  **Limited Unit Tests**: Only 2 unit test files for a large codebase

---

## Gap Analysis

### Coverage Gaps

| Layer | Current Coverage | Target Coverage | Gap |
|-------|------------------|-----------------|-----|
| **Input Adapters** | ✅ Excellent (WhatsApp) | Add Slack, generic edge cases | Slack adapter E2E needed |
| **Core Pipeline** | ⚠️  Partial (golden test broken) | Full orchestration E2E with deterministic agent | Fix golden test, add windowing tests |
| **Output Adapters** | ❌ None | MkDocs + Eleventy E2E | Missing entirely |
| **Schema Validation** | ⚠️  Implicit | Explicit IR schema validation | Add validation assertions |
| **State/Checkpointing** | ⚠️  Partial | Full checkpoint resume tests | Missing checkpoint recovery tests |

### Technical Debt

1. **Pydantic-AI Migration**: Golden fixtures test needs update for new agent pattern
2. **Stage Commands**: `test_stage_commands.py` may reference removed `PipelineStage` abstraction
3. **Temporal Tests**: `test_week1_golden.py` purpose unclear - may be obsolete
4. **Mock Consistency**: Need standardized mocking approach (prefer `pydantic_ai.models.test.TestModel`)

---

## Target Architecture

### Three-Layer E2E Test Structure

```
tests/
├── e2e/
│   ├── input_adapters/           # Layer 1: Input Adapter E2E
│   │   ├── test_whatsapp_adapter.py
│   │   └── test_slack_adapter.py
│   ├── pipeline/                 # Layer 2: Core Pipeline Orchestration E2E
│   │   ├── test_write_pipeline.py
│   │   ├── test_windowing.py
│   │   └── test_checkpointing.py
│   ├── output_adapters/          # Layer 3: Output Adapter E2E
│   │   ├── test_mkdocs_adapter.py
│   │   └── test_eleventy_adapter.py
│   └── cli/                      # CLI E2E (orchestrates all layers)
│       ├── test_write_command.py
│       ├── test_runs_command.py
│       └── test_init_command.py
├── integration/                  # Infrastructure integration tests (no full pipeline)
│   ├── test_rag_store.py
│   ├── test_enrichment_*.py
│   └── test_duckdb_*.py
├── unit/                         # Pure function tests
│   ├── test_formatting.py
│   ├── test_validation.py
│   └── test_utils.py
├── fixtures/
│   ├── inputs/                   # Input test data
│   │   ├── whatsapp_minimal.zip
│   │   ├── whatsapp_edge_cases.zip
│   │   └── slack_export.json
│   └── golden/                   # Expected outputs
│       ├── posts/
│       ├── profiles/
│       └── metadata/
├── cassettes/                    # VCR recordings (integration tests only)
└── helpers/                      # Test utilities (renamed from utils)
    ├── mock_agents.py
    ├── mock_batch_client.py
    └── fixtures.py
```

---

## Refactoring Plan

### Phase 1: Reorganize E2E Tests (Priority: P0)

**Goal**: Establish clear boundaries between test layers without breaking existing tests.

#### Tasks

1. **Create new directory structure**:
   ```bash
   mkdir -p tests/e2e/{input_adapters,pipeline,output_adapters,cli}
   ```

2. **Move and rename files**:
   - `test_whatsapp_real_scenario.py` → `e2e/input_adapters/test_whatsapp_adapter.py`
   - `test_cli_write.py` → `e2e/cli/test_write_command.py`
   - `test_cli_runs.py` → `e2e/cli/test_runs_command.py`
   - `test_cli_utilities.py` → `e2e/cli/test_utilities_command.py`
   - `test_init_template_structure.py` → `e2e/cli/test_init_command.py`

3. **Extract pipeline tests** from `test_whatsapp_real_scenario.py`:
   - Parser tests stay in `test_whatsapp_adapter.py`
   - Full pipeline tests (with writer stubs) → new `e2e/pipeline/test_write_pipeline.py`

4. **Archive temporal tests**:
   - Move `test_week1_golden.py` to `tests/_archive/` with README explaining context
   - Remove if no longer needed after review

5. **Update imports** across all moved files

**Acceptance Criteria**:
- All existing tests pass in new locations
- `pytest tests/e2e/` runs successfully
- No test is lost or duplicated

---

### Phase 2: Fix Golden Fixtures Test (Priority: P0)

**Goal**: Restore the golden fixtures test using the new pydantic-ai pattern.

#### Current Problem

`test_with_golden_fixtures.py` is marked as `xfail` because:
```python
monkeypatch.setattr("egregora.agents.writer.agent.GeminiModel", _make_test_model)
```
This monkeypatching approach no longer works with the new Pydantic-AI agent pattern.

#### Solution

Use `pydantic_ai.models.test.TestModel` properly by injecting it at agent creation time, not via monkeypatch.

#### Tasks

1. **Study current agent initialization** in `src/egregora/agents/writer/agent.py`
2. **Add optional `model` parameter** to `write_posts_with_pydantic_agent`:
   ```python
   def write_posts_with_pydantic_agent(
       table,
       start_time,
       end_time,
       client,
       config=None,
       model=None,  # NEW: optional TestModel for testing
   ):
       if model is None:
           model = GeminiModel(...)
       agent = Agent(model=model, ...)
   ```
3. **Update `test_with_golden_fixtures.py`**:
   - Remove monkeypatch of `GeminiModel`
   - Create `TestModel` instance with deterministic tool calls
   - Pass `model=test_model` to pipeline via `WhatsAppProcessOptions`
4. **Verify golden outputs** match expected structure
5. **Remove `@pytest.mark.xfail` decorator**

**Acceptance Criteria**:
- `test_with_golden_fixtures.py` passes without xfail
- Test is deterministic (same output every run)
- Test runs in <5 seconds (no API calls)

---

### Phase 3: Implement Output Adapter E2E Tests (Priority: P1)

**Goal**: Add comprehensive E2E tests for output adapters (currently missing).

#### Test File 1: `test_mkdocs_adapter.py`

```python
"""E2E tests for MkDocs output adapter.

Verifies that internal Document primitives are correctly serialized
into MkDocs site structure (markdown files, YAML frontmatter, config).
"""

def test_mkdocs_adapter_serves_post_document(tmp_path):
    """Test that serving a Post document creates correct markdown file."""
    adapter = MkDocsAdapter(output_dir=tmp_path)

    post_doc = Document(
        kind=DocumentType.POST,
        body_md="# Test Post\n\nThis is content.",
        metadata={
            "title": "Test Post",
            "slug": "test-post",
            "date": "2025-11-19",
            "tags": ["test"],
            "authors": ["uuid-123"],
        },
    )

    adapter.serve(post_doc)

    # Verify file creation
    expected_path = tmp_path / "posts" / "2025-11-19-test-post.md"
    assert expected_path.exists()

    # Verify content
    content = expected_path.read_text()
    assert "# Test Post" in content
    assert "title: Test Post" in content

    # Verify YAML frontmatter
    frontmatter = extract_frontmatter(content)
    assert frontmatter["slug"] == "test-post"
    assert frontmatter["date"] == "2025-11-19"

def test_mkdocs_adapter_serves_profile_document(tmp_path):
    """Test that serving a Profile document updates .authors.yml."""
    # Similar structure...

def test_mkdocs_adapter_handles_slug_collision(tmp_path):
    """Test idempotent overwriting behavior for same slug+date."""
    # Test P1 badge response behavior...
```

#### Test File 2: `test_eleventy_adapter.py`

```python
"""E2E tests for Eleventy Arrow output adapter.

Verifies that documents are buffered and written as Parquet files
with correct schema and content.
"""

def test_eleventy_adapter_buffers_documents(tmp_path):
    """Test that adapter buffers multiple documents before writing."""
    # Test buffering behavior...

def test_eleventy_adapter_writes_parquet_window(tmp_path):
    """Test that finalize_window() writes correct Parquet file."""
    # Test Parquet generation...

def test_eleventy_adapter_parquet_schema_matches_document(tmp_path):
    """Test that Parquet schema matches Document primitive columns."""
    # Test schema validation...
```

**Acceptance Criteria**:
- Both adapter E2E test files created
- 100% coverage of adapter `serve()` and `finalize_window()` methods
- All tests deterministic and fast (<2 seconds)

---

### Phase 4: Add Schema Validation Assertions (Priority: P1)

**Goal**: Make IR_MESSAGE_SCHEMA validation explicit in all pipeline E2E tests.

#### Current State

Schema validation happens implicitly through code execution. If schema changes break tests, the error is unclear.

#### Target State

Every E2E test that works with Ibis tables should explicitly validate schema:

```python
from egregora.database.validation import validate_ir_schema

def test_whatsapp_parser_produces_valid_ir(whatsapp_fixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    # EXPLICIT VALIDATION
    validate_ir_schema(table)  # Will raise ValidationError if schema mismatches

    # Then continue with other assertions...
    assert table.count().execute() > 0
```

#### Tasks

1. **Audit all E2E tests** for tables passed between pipeline stages
2. **Add `validate_ir_schema()` calls** at stage boundaries:
   - After parsing (Input Adapter → IR)
   - After enrichment (IR → IR with egregora messages)
   - After windowing (IR → Window subsets)
   - Before writer (Window → Agent)
3. **Update helper fixtures** to include validation by default
4. **Add schema mismatch tests** (negative tests for invalid schemas)

**Acceptance Criteria**:
- All E2E tests explicitly validate IR schema at stage boundaries
- Tests fail fast with clear error if schema breaks
- Negative tests verify schema validation catches errors

---

### Phase 5: Standardize Mocking Strategy (Priority: P2)

**Goal**: Establish consistent mocking patterns across all test types.

#### Mocking Guidelines

| Test Type | What to Mock | How to Mock | Why |
|-----------|--------------|-------------|-----|
| **Unit** | External dependencies (file I/O, DB, API) | `unittest.mock.patch` | Isolate pure function logic |
| **Integration** | Expensive APIs (Gemini, embeddings) | `pytest-vcr` cassettes | Test real integrations with recorded responses |
| **E2E Input Adapter** | Nothing (use real ZIPs) | N/A | Validate real file parsing |
| **E2E Pipeline** | LLM agent decisions | `pydantic_ai.models.test.TestModel` | Deterministic agent output |
| **E2E Output Adapter** | Nothing (use real file writes) | N/A | Validate real file generation |
| **E2E CLI** | LLM agent decisions | `pydantic_ai.models.test.TestModel` via config | Full CLI integration |

#### Tasks

1. **Document mocking patterns** in `tests/helpers/README.md`
2. **Create reusable mock factories**:
   ```python
   # tests/helpers/mock_agents.py
   def create_deterministic_writer_agent(window_id: str) -> TestModel:
       """Create TestModel that writes deterministic posts/profiles."""
       return TestModel(
           call_tools=["write_post_tool", "write_profile_tool"],
           custom_output_args={...},
           seed=hash(window_id) % 10000,  # Deterministic per window
       )
   ```
3. **Migrate existing tests** to use standard mocks
4. **Remove ad-hoc mocking code** (e.g., `DummyGenaiClient` in `test_whatsapp_real_scenario.py`)

**Acceptance Criteria**:
- All E2E pipeline tests use `TestModel` for agent mocking
- All integration tests use VCR cassettes for API recording
- All mocking code centralized in `tests/helpers/`
- README documents mocking patterns clearly

---

### Phase 6: Add Checkpoint/Resume Tests (Priority: P2)

**Goal**: Validate checkpoint and resume behavior in write pipeline.

#### Test Coverage Needed

```python
def test_write_pipeline_creates_checkpoint(tmp_path):
    """Test that pipeline creates checkpoint on successful completion."""
    # Run pipeline with --resume flag
    # Verify .egregora/checkpoint.json exists
    # Verify checkpoint contains last processed timestamp

def test_write_pipeline_resumes_from_checkpoint(tmp_path):
    """Test that pipeline skips already-processed windows when resuming."""
    # Run pipeline to process first half
    # Verify checkpoint created
    # Run pipeline again with --resume
    # Verify only new windows processed (check mock agent call count)

def test_write_pipeline_rebuilds_without_resume(tmp_path):
    """Test that pipeline processes all windows when --resume not specified."""
    # Run pipeline to completion
    # Run pipeline again WITHOUT --resume
    # Verify all windows reprocessed
```

**Acceptance Criteria**:
- Tests cover checkpoint creation, resume, and full rebuild
- Tests verify checkpoint file contents
- Tests validate observability (run tracking) during resume

---

## Migration Strategy

### Execution Order

1. **Phase 1 (Week 1)**: Reorganize E2E tests → Clear structure, no functionality change
2. **Phase 2 (Week 1)**: Fix golden fixtures → Restore critical E2E coverage
3. **Phase 3 (Week 2)**: Output adapter E2E → Fill major coverage gap
4. **Phase 4 (Week 2)**: Schema validation → Make contracts explicit
5. **Phase 5 (Week 3)**: Standardize mocking → Improve maintainability
6. **Phase 6 (Week 3)**: Checkpoint tests → Complete coverage

### Risk Mitigation

- **Run full test suite after each phase** to catch regressions
- **Keep old tests until new tests pass** (don't delete, move to `_archive/`)
- **Use feature flags** for new test patterns (e.g., `EGREGORA_USE_NEW_MOCKS=1`)
- **Document changes in CHANGELOG** for each phase

### Rollback Plan

If a phase introduces issues:
1. Revert the commit for that phase
2. File GitHub issue with details
3. Continue with remaining phases (most are independent)

---

## Success Criteria

### Quantitative Metrics

- **Test Organization**: 100% of E2E tests in correct layer directory
- **Test Health**: 0 xfail tests, 0 skipped tests (except optional VCR tests)
- **Coverage**: >80% line coverage for pipeline orchestration code
- **Performance**: E2E test suite completes in <60 seconds
- **Determinism**: 100% of E2E tests pass consistently (no flakes)

### Qualitative Metrics

- **Clarity**: New contributor can understand test structure from directory layout
- **Debuggability**: Test failures point to specific layer/component
- **Maintainability**: Adding new test follows clear pattern
- **Documentation**: Test purpose and mocking strategy documented

---

## Implementation Guidelines

### Writing New E2E Tests

#### 1. Input Adapter E2E

```python
"""Pattern: Validate parsing of external format → IR."""

def test_adapter_name_parses_basic_export(fixture):
    """Test that adapter correctly parses typical export."""
    export = create_export_from_fixture(fixture)
    table = adapter.parse(export)

    # ALWAYS validate schema
    validate_ir_schema(table)

    # Verify expected columns exist
    assert {"timestamp", "author", "message"}.issubset(table.columns)

    # Verify data integrity
    assert table.count().execute() > 0

def test_adapter_name_handles_edge_case_X(fixture):
    """Test that adapter gracefully handles edge case X."""
    # Edge cases: multiline messages, attachments, mentions, etc.
```

#### 2. Pipeline Orchestration E2E

```python
"""Pattern: Validate end-to-end orchestration with mocked agent."""

@pytest.fixture
def deterministic_agent():
    """Fixture providing TestModel for deterministic agent output."""
    return create_deterministic_writer_agent(window_id="test-window")

def test_write_pipeline_processes_single_window(tmp_path, deterministic_agent):
    """Test that pipeline processes single window correctly."""
    config = create_test_config(tmp_path)
    options = WhatsAppProcessOptions(
        output_dir=tmp_path,
        step_size=100,
        step_unit="messages",
        model=deterministic_agent,  # Inject mock
    )

    results = process_whatsapp_export(fixture_zip, options=options)

    # Verify run tracking
    run_id = results["run_id"]
    run_record = query_run(run_id)
    assert run_record["status"] == "completed"

    # Verify outputs
    assert (tmp_path / "posts").exists()
```

#### 3. Output Adapter E2E

```python
"""Pattern: Validate Document → file serialization."""

def test_adapter_serves_document_type_X(tmp_path):
    """Test that adapter correctly serves document type X."""
    adapter = AdapterClass(output_dir=tmp_path)
    document = create_test_document(kind=DocumentType.X)

    adapter.serve(document)

    # Verify file creation
    expected_path = tmp_path / "expected" / "path.md"
    assert expected_path.exists()

    # Verify content matches document
    content = expected_path.read_text()
    assert document.body_md in content

    # Verify metadata serialization
    metadata = extract_metadata(content)
    assert metadata["key"] == document.metadata["key"]
```

### Test Naming Conventions

- **Test files**: `test_{component}_adapter.py`, `test_{feature}_pipeline.py`
- **Test functions**: `test_{component}_{action}_{scenario}`
- **Fixtures**: `{component}_fixture`, `{component}_adapter`, `deterministic_{component}`

### Assertions Best Practices

1. **Schema First**: Always validate IR schema before other assertions
2. **State Over Return**: Verify side effects (files, DB rows) not just return values
3. **Specific Errors**: Use `pytest.raises(SpecificError, match="error text")` not `Exception`
4. **Positive + Negative**: Test both success and failure cases

---

## References

- **Current Tests**: `tests/e2e/test_whatsapp_real_scenario.py` (comprehensive example)
- **Mock Infrastructure**: `tests/utils/mock_batch_client.py`
- **Schema Validation**: `src/egregora/database/validation.py`
- **Pydantic-AI TestModel**: https://ai.pydantic.dev/api/models/test/

---

## Appendix: Deprecated Tests Audit

### Files to Archive

| File | Reason | Action | Timeline |
|------|--------|--------|----------|
| `test_week1_golden.py` | Temporal test, unclear purpose | Archive to `_archive/` with README | Phase 1 |
| `test_stage_commands.py` | May reference removed `PipelineStage` | Audit for relevance, archive if obsolete | Phase 1 |

### Files to Refactor

| File | Issue | Solution | Timeline |
|------|-------|----------|----------|
| `test_with_golden_fixtures.py` | Marked as xfail | Fix pydantic-ai mocking | Phase 2 |
| `test_whatsapp_real_scenario.py` | Mixes parser + pipeline concerns | Split into two files | Phase 1 |

---

**Document Version**: 1.0
**Last Updated**: 2025-11-19
**Status**: Draft - Ready for Review
