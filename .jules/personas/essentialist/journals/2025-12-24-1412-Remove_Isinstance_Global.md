---
title: "💎 Remove Isinstance Global"
date: 2025-12-24
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-24 - Removing `isinstance` from Jinja Environment
**Observation:** The `isinstance` function was injected as a global into the Jinja2 environment in `src/egregora_v3/core/types.py`. This is a clear violation of the "Data over logic" heuristic, as it encourages imperative branching within a declarative template system. Although the template itself had been refactored to use a data property (`is_document`), this dead configuration remained, posing a risk of future regressions.

**Action:** I removed the `isinstance` global from the Jinja environment. Following a strict Test-Driven Development (TDD) approach, I first added a failing test to `tests/v3/core/test_types.py` that asserted the absence of the global. After removing the offending line from `src/egregora_v3/core/types.py`, the new test passed, along with all other existing tests, ensuring the change was safe and effective.
