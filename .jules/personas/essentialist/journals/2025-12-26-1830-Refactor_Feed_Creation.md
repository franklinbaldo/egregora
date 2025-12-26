---
title: "💎 Refactor Feed Creation to be Declarative"
date: 2025-12-26
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-26 - Summary

**Observation:** The `documents_to_feed` function in `src/egregora_v3/core/types.py` was a standalone function that imperatively handled the logic for creating a `Feed` object from a list of `Document` objects. This violated the "Declarative over imperative" and "Data over logic" heuristics, as the responsibility for constructing a `Feed` should belong to the `Feed` model itself.

**Action:** I refactored the codebase to align with these heuristics.
1. I created a new test file, `tests/v3/core/test_feed.py`, and wrote a failing test for a new, declarative `Feed.from_documents` factory method, following a strict Test-Driven Development (TDD) process.
2. I implemented the `Feed.from_documents` class method on the `Feed` model, moving the logic from the old `documents_to_feed` function into it.
3. I replaced all usages of the old function in the test suite with calls to the new factory method.
4. I deleted the now-unused `documents_to_feed` function.
5. I ran pre-commit checks and the full test suite to ensure the changes were safe and correct.

**Reflection:** This refactoring is a strong example of the "Data over logic" heuristic. By moving the creation logic into a factory method on the `Feed` model, the code is now more object-oriented, discoverable, and easier to maintain. The `Feed` class is now responsible for its own construction, which makes the API more intuitive. Future work should investigate other core data models for similar opportunities to replace imperative helper functions with declarative factory methods or validators.
