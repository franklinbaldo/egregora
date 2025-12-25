---
title: "💎 Reverted Concept Refactor"
date: 2025-12-25
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Reverted Concept Refactor
**Observation:** The `WikiPage.create_concept` factory in `src/egregora_v3/knowledge/concepts.py` appeared to be a violation of the "Declarative over imperative" heuristic due to its complex, multi-step creation logic.

**Action:** I attempted to refactor the factory to a simple, declarative constructor call, following a strict TDD process. I created a test file and a test to lock in the behavior. However, the refactoring caused test failures, revealing that the direct Pydantic constructor was incompatible with the parent `Document` class's design. The parent's `create` method contains essential logic that is bypassed when calling the subclass constructor directly. Recognizing this, I reverted all changes, deleting the new test file and restoring `concepts.py` to its original state.

**Reflection:** The root issue is not in `WikiPage`, but in the design of the `Document` base class. Its `create` factory method is not designed for easy extension by subclasses, forcing them into imperative workarounds. This violates the "Composition over inheritance" and "Interfaces over implementations" heuristics at a deeper level. A future refactoring effort should focus on the `Document` class itself. The goal would be to make its initialization logic composable, perhaps by moving the slug/ID generation into a separate, reusable function or a `post_init` validator, allowing subclasses like `WikiPage` to use a simple, declarative constructor without breaking fundamental invariants. This would be a higher-leverage change that would simplify not just `WikiPage`, but any other `Document` subclass.
