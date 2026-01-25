# RFC 028: The Active Maintainer

**Status:** Proposed
**Date:** 2026-01-26
**Author:** Visionary 🔭
**Disruption Level:** High (Moonshot)

## 1. Problem Statement
**Assumption:** "Egregora is a **passive observer** that documents the past, and maintenance requires **human intervention**."

Technical debt accumulates faster than humans can fix it. As highlighted in `ARCHITECTURE_ANALYSIS.md`, core files like `write.py` have grown to unmanageable sizes (1400+ lines), and test coverage is low (39%). Humans prioritize new features over refactoring, leading to "bit rot" and increasing fragility. We treat Egregora as a tool we *use*, not a teammate that *helps*.

## 2. Proposed Solution
**Vision:** Transform Egregora into an **Active Maintainer**—an autonomous agent capable of modifying its own codebase to improve health, consistency, and performance.

Instead of just *reading* code to write documentation, Egregora will *read* code to fix it. It will operate in a "Janitor" loop:
1.  **Scan**: Identify code smells (complex functions, missing docstrings, dead code).
2.  **Plan**: Propose a refactoring strategy.
3.  **Act**: Generate a PR with the fix.
4.  **Verify**: Ensure tests pass (leveraging the "Dry Run" capability).

**Key Capabilities:**
*   **Auto-Refactoring**: Breaking down large functions (e.g., splitting `write.py`).
*   **Auto-Documentation**: Adding missing docstrings based on code analysis.
*   **Debt Collection**: converting `TODO` comments in code into actual GitHub Issues or PRs.

## 3. Value Proposition
*   **Zero-Friction Maintenance**: Technical debt is paid down continuously, not in "Refactoring Sprints".
*   **Higher Quality**: Consistent enforcement of standards (docstrings, typing) across the entire codebase.
*   **Team Velocity**: Developers focus on "Vision" and "Architecture", leaving "Chore" work to the AI.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Autonomous Code Refactoring
  As a Developer
  I want Egregora to automatically identify and fix code quality issues
  So that I can focus on high-level feature work

Scenario: Splitting a complex function
  Given a Python file "src/legacy.py" containing a function with cyclomatic complexity > 15
  And the "Active Maintainer" agent is enabled
  When the agent runs its nightly scan
  Then it should identify the complex function
  And it should propose a refactor extracting logic into 3 smaller helper functions
  And it should generate a Pull Request named "refactor: simplify legacy.py"
  And the PR should pass all existing unit tests

Scenario: Auto-generating missing docstrings
  Given a function "calculate_metrics" in "src/stats.py" without a docstring
  When the "Active Maintainer" scans the file
  Then it should analyze the function body to understand its behavior
  And it should create a PR adding a Google-style docstring to "calculate_metrics"
  And the docstring should correctly describe arguments and return types

Scenario: Safety Interlock (Sandboxing)
  Given the agent proposes a change that causes tests to fail
  When the verification step runs
  Then the agent should discard the changes
  And it should log the failure reasoning to "journals/maintenance_log.md"
  And it should NOT open a PR
```

## 5. Implementation Hints
*   **Agent**: Create a new `JanitorAgent` using `pydantic-ai`.
*   **Tools**: Give the agent access to `ast` (Abstract Syntax Tree) parsing and `git` CLI.
*   **Safety**: The agent must run in a strict sandbox (containerized) and cannot push directly to `main`.
*   **Governance**: Use `PROMPTS.md` to strictly define "Allowed Refactoring Types" to prevent architectural drift.

## 6. Risks
*   **Hallucinated Logic**: The AI might subtly change business logic while refactoring.
    *   *Mitigation*: Strict requirement for passing existing tests. If coverage is low, the agent is forbidden from touching that module.
*   **PR Noise**: Flooding the team with trivial PRs.
    *   *Mitigation*: Rate limit to 1 PR per day.
*   **Infinite Loops**: "Fixing" the same code back and forth.
    *   *Mitigation*: Track file hashes and "ignore" lists.
