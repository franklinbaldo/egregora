# Plan: Visionary - Sprint 2

<<<<<<< HEAD
<<<<<<< HEAD
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
=======
**Persona:** Visionary 🔭
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to prepare the architecture for "Autopoiesis" (RFC 028) by defining the data structures for self-reflection.

- [ ] **Define Reflection Schema:** Create the Pydantic models for the "System Feedback" section of the journal. This turns unstructured text into actionable data.
- [ ] **Design Prompt Optimizer CLI:** Create the design spec for `egregora optimize-prompts` (RFC 029), including the "Human-in-the-loop" PR workflow.
- [ ] **Security Collaboration:** Work with Sentinel to define the "Mutation Sandbox" to prevent prompt injection attacks via the journal.

## Dependencies
- **Simplifier:** I need `write.py` decomposed so I can hook into the journal generation process cleanly.
- **Sentinel:** I need the "SecretStr" implementation to ensure my optimizer doesn't leak secrets.

## Context
We are moving from a "Batch/Static" era to a "Living System" era. Sprint 2 is about creating the *language* of this evolution. If we can't structure the feedback, we can't act on it.

## Expected Deliverables
1.  **Schema Module:** `src/egregora/reflection/models.py` (Draft).
2.  **Design Doc:** `docs/design/reflective-optimizer.md`.
3.  **RFCs:** 028 and 029 finalized and merged.
>>>>>>> origin/pr/2876

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
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
=======
| Schema is too rigid | Medium | Medium | I will analyze past journals to ensure the schema covers existing feedback patterns. |
| Security concerns block Autopoiesis | Medium | High | I will co-design with Sentinel from Day 1 to ensure safety is built-in. |

## Proposed Collaborations
- **With Sentinel:** To design the "Mutation Sandbox".
- **With Simplifier:** To align on where the `Reflection` module sits in the new architecture.
>>>>>>> origin/pr/2876
=======
**Persona:** Visionary 🔭
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives

My mission for this sprint is to deliver the "Dry Run Mode" (Quick Win) to enable cost control and pave the way for autonomous agents.

- [ ] **Core Logic Implementation:** Implement the `dry_run` flag in `write.py` and the `TokenEstimator` service (RFC 029).
- [ ] **Reporting UI:** Create the `DryRunReporter` to visualize estimated costs and window breakdowns using `rich`.
- [ ] **CLI Integration:** Expose `--dry-run` in the `egregora write` command.
- [ ] **Verification:** Ensure dry run performance is under 5 seconds for standard inputs.

## Dependencies

- **Bolt:** I need to ensure that my token estimation logic doesn't introduce performance regressions (e.g., re-reading files unnecessarily).
- **Scribe:** Documentation needs to be updated to explain the new flag and how to interpret the cost estimates.

## Context

We identified that running the pipeline is opaque and costly. Before we can build "The Active Maintainer" (Moonshot), we need a simulation layer. This sprint delivers that layer immediately as a user-facing feature (`--dry-run`).

## Expected Deliverables

1.  `--dry-run` flag working in `egregora write`.
2.  `TokenEstimator` service with unit tests.
3.  Cost estimation logic for Gemini models.
4.  Updated CLI help text.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Inaccurate Estimates | Medium | Low | Clearly label output as "Estimated" and add a disclaimer. |
| Code Complexity | Medium | Medium | Use the "Facade Pattern" to abstract the LLM calls so `write.py` doesn't become a mess of `if dry_run:` checks. |

## Proposed Collaborations

- **With Bolt:** Review the `TokenEstimator` for efficiency.
- **With Scribe:** Co-author the "Cost Management" section in the docs.
>>>>>>> origin/pr/2835
