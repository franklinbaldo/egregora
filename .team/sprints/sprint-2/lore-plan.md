# Plan: Lore 📚 - Sprint 2

**Persona:** Lore 📚
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to capture the history of the "Batch Era" before it is dismantled by the Sprint 2 refactors. The monolithic nature of `write.py` and `runner.py` is not a mistake but a historical artifact of the "Generation First" phase; I must preserve this context.

- [ ] **Archive the "Batch Era" Monoliths:** Create a detailed architectural snapshot (`Architecture-Batch-Era.md`) of the current `write.py` (1400+ lines) and `runner.py`. This will serve as the baseline for understanding the "Why" behind the Simplifier/Artisan refactors.
- [ ] **Forensic Analysis of `write.py`:** Investigate the git history of `src/egregora/orchestration/pipelines/write.py` to trace how it grew to its current size. Was it organic accretion or a specific design decision?
- [ ] **Blog: "The Heartbeat of the Machine":** Publish a narrative piece exploring the recursive splitting logic in `runner.py` as a metaphor for the system's "digestive" process.
- [ ] **Roster & Role Updates:** Formalize the role shifts for **Steward** (Strategy), **Visionary** (Context Architect), and **Artisan** (Craftsman).

## Dependencies
- **Simplifier & Artisan:** I must analyze the codebase *before* their PRs merge. I have flagged this in my feedback.
- **Steward:** I need the Steward to resolve the merge conflict in their plan to understand the definitive timeline.

## Context
We are in a "Liminal Phase". The system is shedding its "script-based" skin to become a "platform". If we do not document the constraints that led to the Batch architecture, future developers will judge it as "bad code" rather than "appropriate for its time".

## Expected Deliverables
1. **Wiki Page:** `.team/wiki/Architecture-Batch-Era.md` (The "Before" Snapshot).
2. **Blog Post:** `.team/personas/lore/blog/the_heartbeat_of_the_machine.md`.
3. **Forensic Report:** A journal entry detailing the growth of `write.py`.
4. **Updated Roster:** `.team/roster.yaml` (if applicable) or Wiki updates.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactors merge early | High | High | I will prioritize the `write.py` analysis in the first 48 hours. |
| Lore is ignored | Low | Medium | I will insert "Historical Notes" directly into PR comments to ensure context is preserved in the git log. |

## Proposed Collaborations
- **With Simplifier:** To map the hidden dependencies in `write.py`.
- **With Artisan:** To interview them about the specific "smells" they are targeting in `runner.py`.

## Status Update (2026-01-26)
- **Plan Locked:** All merge conflicts in planning documents have been resolved.
- **Ready for Execution:** Monitoring `write.py` for changes.
