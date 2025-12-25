---
title: "💎 Simplify WriterAgent Dependencies"
date: 2025-12-25
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Simplify WriterAgent Dependencies
**Observation:** The `WriterAgent` in `src/egregora_v3/engine/agents/writer.py` violated the "Constraints over options" and "Explicit over implicit" heuristics. It used a boolean flag (`use_templates`) to switch between two different implementations for prompt generation (hardcoded vs. template-based), creating unnecessary complexity. It also contained special logic to handle a "test" model string, a "smart default" that hid its actual dependency.

**Action:** I refactored the `WriterAgent` to align with Essentialist principles. I removed the `use_templates` flag and all hardcoded prompt logic, enforcing a single, declarative path. The constructor now requires a Pydantic-AI model instance and a `TemplateLoader`, making its dependencies explicit. This entire process was guided by Test-Driven Development, which included merging two test files, creating a failing test to enforce the new design, and then implementing the changes to make the tests pass.

**Reflection:** This refactoring demonstrates how explicit dependency injection simplifies components. By removing the internal logic that decided *how* to build a prompt or *what* model to use, the `WriterAgent` is now a more predictable orchestrator of its dependencies. In the next iteration, I should investigate the `EnricherAgent` for similar patterns of conditional logic or implicit dependencies that can be simplified.
