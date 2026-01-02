---
title: "💎 Refactor V3 Banner Generator"
date: 2025-12-30
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-30 - Summary

**Observation:** The V3 banner generation engine in `src/egregora_v3/engine/banner/` contained a class, `GeminiV3BannerGenerator`, that was an unnecessary abstraction over a single API call. This violated the "Small modules over clever modules" heuristic.

**Action:** I refactored the banner generation logic to be simpler and more direct, following a strict Test-Driven Development process.
1.  **RED:** I created a new test file for a standalone `generate_image_with_gemini` function, which initially failed.
2.  **GREEN:** I implemented the new function in `generator.py`, moving the logic from the old class and then deleting the class.
3.  **REFACTOR:** I updated the `FeedBannerGenerator` to use the new function, replacing the `ImageGenerationProvider` dependency with a direct call. I then refactored all related tests, deleting obsolete files and fixing others to align with the new, simpler design. I also fixed a bug in my test mock that was causing failures.

**Reflection:** This refactoring is a good example of how removing unnecessary layers of abstraction can lead to simpler, more maintainable code. The `ImageGenerationProvider` protocol was not providing any value in this context, and replacing the class with a function made the code easier to understand and test. The TDD process was essential for making this change safely, and the test failures correctly guided me to fix all the downstream consequences of the refactoring. Future work should continue to look for similar opportunities to remove unnecessary abstractions, especially in the v3 engine.
