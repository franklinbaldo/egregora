---
title: "💎 refactor(v3): Simplify banner generator"
date: 2025-12-28
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-28 - Summary

**Observation:** The `FeedBannerGenerator` in `src/egregora_v3/engine/banner/feed_generator.py` violated several Essentialist Heuristics. It used unnecessary adapter classes (`BannerTaskEntry`, `BannerGenerationResult`) and imperative logic, making it overly complex. This is a violation of "Small modules over clever modules" and "Declarative over imperative".

**Action:** I refactored the banner generation logic following a strict Test-Driven Development (TDD) process.
1.  **RED:** Wrote a failing test for a new, standalone `generate_banner_document` function.
2.  **GREEN:** Implemented the new function, consolidating all banner creation logic into a single, data-oriented function.
3.  **REFACTOR:**
    *   Modified the `FeedBannerGenerator` to use this new function, turning it into a simple orchestrator.
    *   Deleted the now-unused `BannerTaskEntry` and `BannerGenerationResult` classes.
    *   Cleaned up the test suite, removing obsolete tests and adding coverage for the failure path in the new function, as identified during code review.

**Reflection:** This refactoring is a strong example of how applying the "Data over logic" and "Small modules over clever modules" heuristics can dramatically simplify code. By extracting the core logic into a pure function, the `FeedBannerGenerator` class became much cleaner and more declarative. The initial code review missed a test case, which highlights the importance of comprehensive testing, especially for error-handling paths. Future work should continue to look for complex classes that can be simplified by extracting their core logic into smaller, reusable functions.
