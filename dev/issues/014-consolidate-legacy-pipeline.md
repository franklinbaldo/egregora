# Issue #014: Consolidate and Deprecate Legacy `pipeline.py` Module

- **Status**: Proposed
- **Type**: Refactoring / Technical Debt
- **Priority**: High
- **Effort**: Medium

## Problem

The new, DataFrame-native `UnifiedProcessor` in `src/egregora/processor.py` is the path forward documented in ADR-006. The legacy `src/egregora/pipeline.py` module still contains helpers such as `_prepare_transcripts` and `build_llm_input`, creating two overlapping sources of truth for the processing pipeline.

The coexistence of both paths increases maintenance overhead, makes the call graph harder to trace, and creates confusion for contributors who are trying to understand which module should be extended.

## Proposal

1. **Audit `pipeline.py`.** Document every function and classify it as:
   - Still used by `UnifiedProcessor` (needs a new home).
   - Obsolete/dead code (ready for deprecation and removal).
   - Generic helper that should live in a shared utilities module.
2. **Relocate live helpers.** Move the functions still required by `UnifiedProcessor` into more appropriate modules. For example, transcript munging helpers could become private functions on `UnifiedProcessor` or move into a new `egregora/transcript_utils.py` module, while general-purpose utilities could live under `egregora/utils.py`.
3. **Add deprecation warnings.** For any remaining legacy entry points that cannot yet be removed, emit `DeprecationWarning` with guidance that developers should migrate to `UnifiedProcessor`.
4. **Update call sites and tests.** Ensure all callers use the new locations, update imports, and adjust tests accordingly.
5. **Plan removal.** Once no internal callers rely on `pipeline.py`, delete the module to prevent regressions.

## Expected Benefits

- Eliminates duplicated logic and conflicting abstractions.
- Establishes `UnifiedProcessor` as the single source of truth for pipeline behavior.
- Makes onboarding easier by reducing the amount of historical context required.
- Aligns the codebase with the architecture decisions captured in ADR-006.

## Dependencies

- Understanding of the refactor captured in ADR-006 and how existing commands rely on `UnifiedProcessor`.
- Coordination with any work that still depends on the legacy pipeline, to avoid breaking users mid-transition.
