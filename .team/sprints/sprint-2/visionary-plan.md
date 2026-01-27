# Plan: Visionary - Sprint 2

<<<<<<< HEAD
**Persona:** Visionary
**Sprint:** 2
**Created:** 2026-01-22
**Priority:** High

## Objectives
Describe the main objectives for this sprint:

- [ ] Prototype `CodeReferenceDetector` for path and SHA detection in chat messages (RFC 027).
- [ ] Implement POC of `GitHistoryResolver` to map Timestamp -> Commit SHA (RFC 027).
- [ ] Validate feasibility of integration with Writer agent's Markdown.

## Dependencies
- **builder:** Support for Git Lookups cache schema in DuckDB.
- **scribe:** Documentation update to include new historical links feature.

## Context
After approval of the Quick Win (RFC 027), the focus is to validate the core technology (Regex + Git CLI) before fully integrating into the pipeline. We need to ensure that detection is precise and commit resolution is fast.

## Expected Deliverables
1. Python script `detect_refs.py` that extracts references from a text file.
2. Python script `resolve_commit.py` that accepts date/time and returns SHA from local repo.
3. Performance report (time per lookup).

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Slow Git Lookup | High | Medium | Implement aggressive caching (DuckDB/Redis) |
| Path ambiguity | Medium | Low | Link to tree root or display warning if file does not exist |

## Proposed Collaborations
- **With builder:** Define `git_cache` table schema.
- **With artisan:** Review resolver code for optimization.

## Additional Notes
Total focus on "Foundation" for the Context Layer.
=======
**Persona:** Visionary 🔭
**Sprint:** 2
**Created:** 2026-01-28
**Priority:** High

## Objectives

My mission is to validate the "Self-Optimizing" capabilities (RFC 029) while maintaining momentum on the "Context Layer" (RFC 027).

- [ ] **Prototype `CriticAgent` (RFC 029):** Design and implement a standalone agent that can take a (Input, Prompt, Output) tuple and return a structured critique.
- [ ] **Validate Code Linking (RFC 027):** (Carried over) Complete the `CodeReferenceDetector` prototype to ensure we can reliably detect file paths in chat.
- [ ] **Update RFCs:** Formalize the learnings from the prototypes into the RFC documents.

## Dependencies

- **Simplifier:** I need a stable `write.py` / `runner.py` structure to know where to "hook" the `CriticAgent`.
- **Builder:** Need support for persisting the `Reflection` artifacts (scoring/critiques).

## Context

Sprint 2 is about "Structure". My contribution is structural *introspection*. By building the `CriticAgent` now, we provide the "eyes" for the system to see itself. This aligns with the polishing phase—we are building the tool that helps us polish.

## Expected Deliverables

1.  **`src/egregora/agents/critic.py`:** A working Pydantic-AI agent for critique.
2.  **`tests/prototypes/test_critic.py`:** Verification that the critic can catch bad prompts.
3.  **`detect_refs.py`:** (RFC 027) Prototype for detecting code references.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Critic is hallucination-prone | High | High | Use "Few-Shot" prompting in the Critic's system prompt to ground it. |
| Overloading Sprint 2 | Medium | Medium | RFC 029 is the priority. RFC 027 can slip to Sprint 3 if needed. |

## Proposed Collaborations

- **With Simplifier:** To agree on the `PipelineContext` structure the Critic will analyze.
- **With Artisan:** To review the `CodeReferenceDetector` regex logic.
>>>>>>> origin/pr/2895
