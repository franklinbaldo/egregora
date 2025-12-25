---
title: "💎 Decouple Core Filters"
date: 2025-12-25
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Decoupling Core Filters
**Observation:** The core types module (`src/egregora_v3/core/types.py`) contained private filter functions (`_format_datetime`, `_normalize_content_type`) that were tightly coupled to its Jinja2 environment. This violated the "Small modules over clever modules" heuristic by mixing data transformation logic with data type definitions.

**Action:** I refactored the code to decouple the filters into a dedicated module, making them reusable and simplifying the `types.py` module. Following a strict Test-Driven Development (TDD) process, I first created a new test file to lock in the existing behavior. Then, I extracted the functions into a new `src/egregora_v3/core/filters.py` module. Finally, I updated `types.py` to import and use the new public functions, removing the now-redundant private implementations. All tests passed, confirming the change was safe and effective.
