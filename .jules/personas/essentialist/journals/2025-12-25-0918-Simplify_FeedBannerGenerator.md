---
title: "💎 Simplify FeedBannerGenerator"
date: 2025-12-25
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Simplify FeedBannerGenerator
**Observation:** The `FeedBannerGenerator` in `src/egregora_v3/engine/banner/feed_generator.py` violated the "One good path over many flexible paths" and "Small modules over clever modules" heuristics. It contained multiple, branching execution paths for batch, sequential, and default generation, mixing orchestration logic with provider-specific details.

**Action:** I refactored the module to have a single, explicit path for banner generation. I removed the complex batching and fallback logic, making the generator a simple orchestrator that requires a provider. The entire process was guided by Test-Driven Development (TDD), starting with the creation of a new test suite to lock in the correct behavior before refactoring.

**Reflection:** This change significantly reduced the module's complexity, making it easier to understand, test, and maintain. The explicit dependency on a provider improves the system's robustness by eliminating hidden "smart" defaults. This pattern of simplifying complex components by removing flexible-but-unnecessary execution paths should be applied to other parts of the engine, particularly the agent and tool-loading mechanisms.
