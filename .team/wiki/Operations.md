# Operational Protocols

> **Status:** Active
> **Last Updated:** 2026-02-02

This document outlines the operational procedures for the JULES autonomous team.

## 🔄 Session Management

### The "Direct Main" Protocol

As of Feb 2026, the JULES system operates on a simplified session model known as the **Direct Main Protocol**.

#### 1. Session Start
- Each persona session initializes by pulling the latest state directly from the `main` branch.
- This ensures that every agent is working with the most up-to-date code and documentation.
- **Historic Context**: Previously, a complex "Sync Layer" attempted to mediate state between sessions, but this introduced unnecessary friction and merge conflicts. The current approach favors a "Fresh Start" mentality.

#### 2. Execution
- Personas perform their tasks (coding, documenting, testing) in an isolated environment.
- Changes are verified locally using standard tools (`pytest`, `pre-commit`).

#### 3. Submission (The `jules` Branch)
- When work is complete, personas do **not** commit to `main` directly.
- Instead, they submit a Pull Request targeting the `jules` branch.
- This creates a review buffer where CI/CD checks can run before the code is merged into the canonical history.

## 🌿 Branching Strategy

| Branch | Purpose | Access |
| :--- | :--- | :--- |
| **`main`** | The canonical source of truth. Stable and deployable. | **Read-Only** for Personas (except via Merge) |
| **`jules`** | The integration branch for autonomous sessions. | **Write** Target for PRs |
| **`feature/*`** | Human-led feature branches. | **Write** for Humans |

## 🤖 CI/CD Integration

- **Auto-Merge**: Valid PRs from trusted personas are eligible for auto-merge if all status checks pass.
- **Status Checks**: Includes linting (`ruff`), strict type checking (`mypy`), and test suites (`pytest`).
