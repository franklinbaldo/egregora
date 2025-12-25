---
title: "💎 Refactor RSS Adapter for Data-Driven Simplicity"
date: 2025-12-25
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Refactoring the RSS Adapter
**Observation:** The `RSSAdapter` in `src/egregora_v3/infra/adapters/rss.py` had two violations of the Essentialist Heuristics. It used an imperative `if/elif` block to dispatch parsing logic based on the feed type, violating the "Data over logic" principle. Additionally, the security-hardened XML parser was configured identically in two separate methods (`parse` and `parse_url`), violating the "Don't Repeat Yourself" (DRY) principle.

**Action:** I refactored the `RSSAdapter` to align it with the heuristics. Following a strict Test-Driven Development (TDD) process, I first added a failing test to assert the existence of a data-driven dispatch mechanism. Then, I replaced the conditional `if/elif` block with a declarative dispatch dictionary that maps feed type tags to their respective parsing methods. I also consolidated the duplicated XML parser setup into a single private helper method. All tests passed, confirming the changes were safe and effective.

**Reflection:** The `RSSAdapter` is now simpler, more maintainable, and a better example of the "Data over logic" principle. This refactoring demonstrates how replacing imperative branching with declarative data structures improves code quality. The next iteration should investigate the `infra/sinks` directory to identify and refactor similar patterns of imperative, type-based dispatch logic.
