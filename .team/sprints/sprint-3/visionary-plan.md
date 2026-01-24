# Plan: Visionary - Sprint 3

**Persona:** Visionary 🔭
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to deliver "The Tuning Fork" - the first step towards the Autonomous Director.

- [ ] **Implement `egregora tune` CLI:** Build the interactive command that allows users to optimize a specific post.
- [ ] **Implement `PromptManager`:** Create the persistence layer that saves user preferences (e.g., "Make it funny" -> maps to specific system instructions).
- [ ] **User Feedback Loop:** Ensure the tuning choices are logged to a dataset that can be used to train/refine future models (local learning).

## Dependencies
- **Simplifier:** I depend on the `write.py` refactor being stable so I can hook into the generation pipeline.
- **Artisan:** I depend on the new Pydantic configuration to store the "Tuned Prompts" cleanly.

## Context
After prototyping in Sprint 2, Sprint 3 is about shipping. "The Tuning Fork" will be the first feature that gives users *control* over the AI without requiring them to be *AI engineers*. This sets the stage for the full "Autonomous Director" in later sprints.

## Expected Deliverables
1. **New Command:** `egregora tune <post_id>`
2. **New Module:** `src/egregora/steering/prompt_manager.py`
3. **Docs:** "How to Tune Your Egregora" guide.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Complexity Creep | Medium | Medium | I will strictly scope `tune` to modifying *system instructions* only, not the full Jinja template structure, for V1. |
| User Confusion | Medium | High | The CLI UX must be intuitive. I will use `rich` extensively to show "Before/After" diffs clearly. |

## Proposed Collaborations
- **With Curator:** Review the "Before/After" presentation in the CLI to ensure it aligns with UX standards.
