# Plan: Essentialist - Sprint 2

**Persona:** Essentialist 💎
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to decouple the pipeline core from the CLI interface, adhering to "Library over framework".

- [ ] **Extract CLI Logic:** Move `run_cli_flow` and argument parsing logic from `src/egregora/orchestration/pipelines/write.py` to `src/egregora/cli/commands/write.py`.
- [ ] **Purify Pipeline:** Ensure `write.py` only contains orchestration logic, callable by any consumer (CLI, script, server), not just CLI arguments.
- [ ] **Unified Config:** Simplify how configuration is loaded and overridden, ensuring "One good path" for config resolution.

## Dependencies
- **Simplifier:** Coordination on `write.py` changes. I will focus on the interface/CLI boundary, Simplifier focuses on internal ETL breakdown.

## Context
Currently, `write.py` mixes CLI argument parsing, configuration merging, and pipeline execution. This makes it hard to invoke the pipeline programmatically or test it without simulating CLI args.

## Expected Deliverables
1.  Clean `write.py` with `run()` as the primary entry point, accepting typed `PipelineRunParams`.
2.  New/Updated `src/egregora/cli/commands/write.py` handling all CLI-specifics (Click/Typer logic).

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Conflict with Simplifier | Medium | Medium | Clear boundaries: I own the "top" (CLI -> Pipeline), Simplifier owns the "inside" (Pipeline -> ETL). |
