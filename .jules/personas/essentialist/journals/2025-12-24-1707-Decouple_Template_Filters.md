---
title: "💎 Decouple Template Filters"
date: 2025-12-24
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-24 - Decouple Template Filters
**Observation:** The `TemplateLoader` class in `src/egregora_v3/engine/template_loader.py` contained private filter methods (`_filter_format_datetime`, etc.). This violated the "Small modules over clever modules" heuristic by coupling pure data transformation logic to a specific loader implementation.
**Action:** I refactored the code to decouple the filters. Following a strict Test-Driven Development (TDD) process, I first created a new test file for the filters. Then, I extracted the filter functions into a new, dedicated module: `src/egregora_v3/engine/filters.py`. Finally, I updated the `TemplateLoader` to import and use these public functions, removing the now-redundant private methods. This change makes the filters reusable and the `TemplateLoader` simpler.
