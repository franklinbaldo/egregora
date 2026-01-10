# Plan: Shepherd - Sprint 2

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 2
**Created:** 2024-07-29 (during Sprint 1)
**Priority:** High

## Goals
My primary goal remains the incremental and sustainable improvement of test coverage. For Sprint 2, I will focus on the next batch of low-coverage, high-impact files and actively collaborate with other personas to ensure new and refactored code is well-tested from day one.

- [ ] **Increase test coverage from 55% to 60%.**
- [ ] **Target key modules:** Focus on `src/egregora/rag/lancedb_backend.py` and `src/egregora/security/` which have significant untested logic.
- [ ] **Collaborate on new features:**
    - Work with **Visionary/Architect/Builder** to define a test strategy for the "Structured Data Sidecar."
    - Work with **Curator** to automate UX validation using browser tests.
- [ ] **Support refactoring efforts:**
    - Provide characterization and TDD testing support for **Refactor's** work on the `issues` module.

## Dependencies
- **Refactor:** The refactoring of the `issues` module will require close collaboration to ensure tests are written before and during the changes.
- **Curator:** The automation of UX tests will depend on the `forge` completing the initial implementation work.

## Context
In Sprint 1, I established the baseline for test coverage at 55.66% and began tackling the lowest-hanging fruit. Sprint 2 is about moving up the stack to more complex but critical areas like the RAG backend and security modules. It's also a crucial time to embed testing culture into the new initiatives proposed by Visionary and the refactoring work planned by Refactor, ensuring quality is built-in, not bolted on.

## Expected Deliverables
1. **Increased Coverage:** The overall test coverage metric will reach at least 60%.
2. **New Test Suites:** New behavioral test files for `lancedb_backend.py` and the `security` modules.
3. **Test Strategy Document:** A brief markdown file outlining the testing approach for the "Structured Data Sidecar."
4. **Automated UX Tests:** A new set of Playwright tests that verify the Curator's UX requirements.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Complex logic is hard to test | Medium | High | Focus on black-box, behavioral testing. Test the public API contract, not the internal implementation. Use `respx` for mocking external services to isolate the component under test. |
| Persona collaboration slows down progress | Low | Medium | Proactively schedule brief, focused pairing sessions. Clearly define the roles: they provide the feature/refactor, I provide the test harness. |

## Proposed Collaborations
- **With Refactor:** Pair-program on the `issues` module, with me writing the tests as they refactor the code.
- **With Curator:** A session to walk through the UX changes, which I will then translate into automated Playwright tests.
- **With Visionary/Architect/Builder:** A planning session to discuss the data schema and observable outputs of the "Structured Data Sidecar" to ensure it's designed for testability.