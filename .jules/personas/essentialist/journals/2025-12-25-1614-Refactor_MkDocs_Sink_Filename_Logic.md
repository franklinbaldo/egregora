---
title: "💎 Refactor MkDocs Sink for Declarative Filename Logic"
date: 2025-12-25
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Refactor MkDocs Sink
**Observation:** The `_get_filename` method in `src/egregora_v3/infra/sinks/mkdocs.py` used an imperative `if/elif` chain to determine the filename for a document. This violated the "Data over logic" and "Declarative over imperative" heuristics.

**Action:** I refactored the method to be declarative. Following a strict TDD process, I first wrote a failing test that explicitly checked the fallback logic (slug -> title -> ID). I then replaced the conditional block with a simple list of filename strategies, iterating through them to find the first valid one. This change simplified the code and aligned it with the Essentialist heuristics.

**Reflection:** The TDD process proved invaluable. The initial test failed because of an unexpected "smart default" in the `Document.create` factory method, which was a separate violation of the "Simple defaults over smart defaults" heuristic. The correct action was not to weaken the production code, but to make the test more explicit by constructing the `Document` object directly. This reinforces that robust, explicit tests are a key tool for enforcing simplicity and identifying hidden complexity at the boundaries of the system.
