---
title: "💎 Refactored MkDocs Sink to Delegate Filtering"
date: 2025-12-27
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-27 - Summary

**Observation:** The `MkDocsOutputSink` in `src/egregora_v3/infra/sinks/mkdocs.py` was re-implementing logic to filter for published documents, a direct violation of the "Data over logic" heuristic. This duplicated functionality already present in the `Feed` model's `get_published_documents` method.

**Action:** I refactored the `MkDocsOutputSink` to be more declarative and less complex. Following a strict Test-Driven Development (TDD) process, I first wrote a failing test to prove that the sink was not using the `Feed` model's filtering method. Then, I modified the sink's `publish` method to call `feed.get_published_documents()`, successfully delegating the filtering responsibility to the data model where it belongs. I also attempted to refactor the `_write_index` method to use a declarative template, but after several failed attempts to perfectly replicate the original output, I pragmatically decided to abandon this change in favor of shipping the core improvement, adhering to the "Shipping over polishing" heuristic.

**Reflection:** This refactoring is another successful application of the "Data over logic" principle. By making the data consumer (`MkDocsOutputSink`) dumber and the data provider (`Feed`) smarter, the system becomes more maintainable and less prone to bugs caused by duplicated logic. The struggle with the template refactoring was a valuable lesson in pragmatism; it's better to ship a valuable, tested improvement than to get stuck on a non-essential detail. Future work should continue to look for opportunities to move logic from infrastructure components into the core data models.
