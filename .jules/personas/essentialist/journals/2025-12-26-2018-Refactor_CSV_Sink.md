---
title: "💎 Refactor CSV Sink to Delegate Filtering"
date: 2025-12-26
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-26 - Summary

**Observation:** The `CSVOutputSink` in `src/egregora_v3/infra/sinks/csv.py` violated the "Data over logic" heuristic. It contained application logic for filtering published documents, mixing data transformation with I/O.

**Action:** I refactored the codebase to delegate this responsibility.
1.  I added a new method, `get_published_documents()`, to the `Feed` model in `src/egregora_v3/core/types.py` to encapsulate the filtering logic.
2.  I refactored the `CSVOutputSink` to use this new method, simplifying it into a pure data publisher.
3.  The entire process was guided by strict TDD. I added a new test for the `Feed` method and a new locking test for the `CSVOutputSink` to ensure the change was safe and correct.

**Reflection:** This change is a good example of the "Data over logic" principle. By making the core `Feed` data model smarter, the surrounding infrastructure (`CSVOutputSink`) becomes simpler and more declarative. The sink no longer needs to know the internal business rules for what "published" means. Future work should continue to inspect other data sinks and consumers to see if similar logic can be pushed down into the core data types, further reducing complexity at the application's edges.
