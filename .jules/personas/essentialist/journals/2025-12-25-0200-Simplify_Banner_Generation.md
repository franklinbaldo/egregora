---
title: "💎 Simplify Banner Generation Logic"
date: 2025-12-25
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Simplify Banner Generation Logic
**Observation:** The banner generation system in `src/egregora_v3/engine/banner/` violated several Essentialist Heuristics. `FeedBannerGenerator` had multiple, complex execution paths (batch vs. sequential, provider vs. default), violating "One good path over many flexible paths." `GeminiV3BannerGenerator` used a broad `except Exception`, violating "Explicit over implicit" by swallowing specific API errors.

**Action:** I refactored the entire banner generation flow following a strict TDD process.
1.  Modified `GeminiV3BannerGenerator` to remove the generic exception handling, allowing specific API errors to propagate.
2.  Simplified `FeedBannerGenerator` by removing the `batch_mode` and the default generator fallback, making the `ImageGenerationProvider` a required dependency. This enforced a single, sequential execution path.
3.  Updated the test suite to reflect these changes, adding a test to ensure exceptions are propagated and removing tests for the deleted features.

**Reflection:** The pattern of optional dependencies and multiple execution paths (`batch_mode`) is a likely source of complexity elsewhere. The next iteration should focus on identifying other modules that offer too much flexibility at the cost of simplicity. For instance, the prompt loading mechanism (`_create_environment`) has a fallback path that could be simplified by requiring an explicit `prompts_dir`. Also, the project lacks a centralized, robust error handling strategy, leading to inconsistent `try...except` blocks; a future task could be to define and enforce a clear error handling policy.
