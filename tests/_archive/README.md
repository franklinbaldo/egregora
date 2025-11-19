# Archived Tests

This directory contains tests that have been archived during the E2E testing refactoring (Phase 1, 2025-11-19).

## Archived Files

### test_week1_golden.py

**Reason**: Temporal test specific to "Week 1" development milestone.

**Status**: Archived pending review - unclear if still needed or if it was a one-time validation test.

**Decision**: Move to archive rather than delete to preserve history. If this test validates specific behavior that should be ongoing, it should be refactored into a properly named E2E test in the appropriate layer.

**Review Date**: 2025-11-19

---

### test_stage_commands.py

**Reason**: May reference removed `PipelineStage` abstraction.

**Status**: Archived pending review - need to verify if this tests functionality that still exists or if it was tied to removed infrastructure.

**Context**: The `PipelineStage` class hierarchy was removed in the 2025-01-12 simplification (see `docs/SIMPLIFICATION_PLAN.md`). All transformations are now pure functions (Table → Table) without the stage abstraction.

**Next Steps**:
1. Review file contents to understand what behavior it tests
2. If testing valid behavior, refactor to use current functional architecture
3. If testing removed infrastructure, can be safely deleted

**Review Date**: 2025-11-19

---

## Restoration Process

If a test needs to be restored:

1. Review the test to understand what it validates
2. Update it to match current architecture (if needed)
3. Move it to the appropriate E2E test layer:
   - `tests/e2e/input_adapters/` - For adapter parsing tests
   - `tests/e2e/pipeline/` - For orchestration tests
   - `tests/e2e/output_adapters/` - For output generation tests
   - `tests/e2e/cli/` - For CLI command tests
4. Update imports and run tests to verify they pass
5. Remove from archive

## Related Documentation

- [E2E Testing Strategy](../../docs/testing/e2e_strategy.md)
- [Simplification Plan](../../docs/SIMPLIFICATION_PLAN.md)
- [Refactoring Plan](../../docs/REFACTORING_PLAN.md)
