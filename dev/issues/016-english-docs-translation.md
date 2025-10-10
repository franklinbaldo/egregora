# Issue #016: Complete English Documentation Translation

- **Status**: Proposed
- **Type**: Documentation
- **Priority**: High
- **Effort**: High

## Problem

The documentation structure is bilingual, but most `docs/en/` pages simply redirect to the Portuguese content. English-speaking users and potential contributors cannot rely on the documentation to understand installation, configuration, or the roadmap, which limits the community reach of the project.

## Proposal

1. **Create a translation tracking plan.** Either open a project board or add a checklist to this issue to enumerate all pages that need translation.
2. **Prioritize critical paths.** Translate the README, quickstart, and user guide first, followed by the developer guide and configuration references. Less critical historical documents (e.g., ADRs) can follow later.
3. **Establish a maintenance workflow.** Whenever new Portuguese content ships, add a stub in the English tree noting that translation is pending. Encourage contributions by labeling these tasks appropriately.
4. **Encourage community involvement.** Advertise the translation needs in contributor docs and issue labels (e.g., `help wanted`, `good first issue`).

## Expected Benefits

- Makes the project accessible to a global audience.
- Improves perceived polish and professionalism.
- Reduces friction for contributors who are more comfortable in English.

## Dependencies

- Coordination with maintainers to review translated content for accuracy.
- Potential automation (e.g., mkdocs plugins) to help detect untranslated pages in the future.
