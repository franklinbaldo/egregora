# Plan: Lore - Sprint 2

**Persona:** Lore 📚
**Sprint:** 2
<<<<<<< HEAD
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to chronicle the "Great Refactor" as it happens, ensuring the transition from the Monolith to the Modular architecture is well-documented.

- [ ] **Chronicle the Great Refactor:** Monitor the PRs from Simplifier (ETL extraction) and Artisan (`runner.py` decomposition). Document the *process* and specific architectural decisions in the Wiki.
- [ ] **Support ADR Process:** Collaborate with Steward to ensure the first set of ADRs are rich in context and historical reasoning, specifically focusing on the "Alternatives Considered" sections.
- [ ] **Blog: "The Monolith Crumbles":** Write a blog post detailing the end of the `write.py` monolith, explaining why it was necessary initially and why it must go now.
- [ ] **Update Wiki Architecture:** Update the Architecture section to reflect the new `src/egregora/orchestration/pipelines/etl/` structure and Pydantic configuration once merged.

## Dependencies
- **Simplifier & Artisan:** I cannot document the new structure until their PRs are up.
- **Steward:** I need the ADR template to be established.

## Context
The "Batch Era" documentation (`Architecture-Batch-Era.md`) was completed in Sprint 1. Now, we are in the active phase of deconstruction. My role shifts from "Snapshotting the Past" to "Recording the Change". The risk of losing "why" decisions is highest during active refactoring.

## Expected Deliverables
1. **Wiki Updates:** Updated Architecture pages reflecting the new modular design.
2. **Blog Post:** "The Monolith Crumbles" (Narrative of the refactor).
3. **ADR Reviews:** Detailed feedback on the first batch of ADRs.
4. **Git Forensics:** Notes on the original implementation of `runner.py` added to the Wiki for posterity.
=======
**Created:** 2026-01-26 (during Sprint 1)
**Priority:** Medium

## Objectives
My mission is to capture the "Deep Knowledge" of the system during this transitional phase.

- [ ] **Wiki - The "Reactive" Shift:** Document the current "Batch Processing" architecture in `.team/wiki/Architecture.md` to establish a baseline before the "Symbiote" changes.
- [ ] **Wiki - Persona Registry:** maintain the `Team-Roster.md` to reflect the evolving roles (e.g., Visionary's new focus).
- [ ] **Blog - "The Great Refactor":** Write a piece in `.team/personas/lore/blog/` documenting the intent behind the major refactors led by Artisan and Refactor.
- [ ] **ADR Indexing:** Collaborate with Steward to link the new ADRs into the Wiki structure.

## Dependencies
- **Steward:** I need the ADR templates and initial records to be established.
- **Visionary:** I need the RFCs to be shared to document their context.

## Context
Sprint 2 is a "Pivot Point." We are changing how we build (ADRs), how we run (Runner refactor), and what we look like (Visual Identity). My job is to ensure we don't lose the history of *what we were* while we become *what we are next*.

## Expected Deliverables
1.  **Updated Wiki:** `Architecture.md` reflecting the "Before" state.
2.  **Blog Post:** "Chronicles of the Refactor."
3.  **ADR Integration:** A section in the Wiki linking to the new ADRs.
>>>>>>> origin/pr/2742

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
| Refactors are purely mechanical and lack context | Medium | High | I will comment on PRs asking for "Why" in docstrings/commit messages. |
| Wiki becomes out of sync with code | High | Medium | I will prioritize Wiki updates immediately after PR merges. |

## Proposed Collaborations
- **With Steward:** Co-authoring the first ADR.
- **With Visionary:** Documenting the context layer prototype.
=======
| Lore Drift | Medium | High | I will monitor PRs closely to ensure documentation keeps pace with code changes. |
| Missing Context | Low | Medium | I will interview personas (via email/tasks) if the "Why" behind a change is unclear. |
>>>>>>> origin/pr/2742
