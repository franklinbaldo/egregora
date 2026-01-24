# Plan: Visionary - Sprint 2

**Persona:** Visionary 🔭
**Sprint:** 2
**Created:** 2026-01-26 (during Sprint 1)
**Priority:** High

## Objectives
My mission is to move from "Manual Prompt Engineering" to "Autonomous Optimization". I will socialize the vision for the "Autonomous Director" and begin prototyping the "Tuning Fork" quick win.

- [ ] **Socialize RFCs:** Present "The Autonomous Director" and "The Tuning Fork" to the team, specifically coordinating with Architect and Builder.
- [ ] **Prototype `egregora tune`:** Build a throwaway script to validate that we can generate meaningful variations of a post using different system prompts.
- [ ] **Research Evaluation Metrics:** Investigate how we can programmatically score "humor", "sentiment", or "coherence" using `pydantic-evals` to support the future Director.

## Dependencies
- **Architect:** I need feedback on where the "Prompt Manager" should live in the new architecture.
- **Builder:** I need to understand the constraints of the `Writer` agent for dynamic prompting.

## Context
In Sprint 1, I identified that users are trapped in a "configuration cage". To change the output style, they must edit Jinja templates. This is a high barrier. "The Tuning Fork" breaks this by allowing interactive, example-based tuning. This sprint is about proving the concept works before we build the CLI.

## Expected Deliverables
1. **Consensus on RFCs:** Agreement from core personas on the direction.
2. **Prototype Script:** `scripts/prototype_tuning.py` demonstrating 3-way prompt variation generation.
3. **Research Note:** A brief document on "Automated Evaluation Strategies" for the Director.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| LLM Variability | High | Medium | The "tuning" might be flaky. I will test with multiple models (Gemini, OpenAI) during prototyping to assess stability. |
| Architecture Conflict | Medium | Medium | I will coordinate early with Steward and Architect to ensure the "Prompt Manager" fits the new V3 design. |

## Proposed Collaborations
- **With Builder:** Pair programming on the prompt variation logic.
