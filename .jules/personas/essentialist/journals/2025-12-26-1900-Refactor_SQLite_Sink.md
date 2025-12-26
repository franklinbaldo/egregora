---
title: "💎 Refactor SQLite Sink for Declarative Serialization"
date: 2025-12-26
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-26 - Summary

**Observation:** The `SQLiteOutputSink` in `src/egregora_v3/infra/sinks/sqlite.py` violated the "Data over logic" and "Small modules over clever modules" heuristics. It mixed data serialization logic (converting a `Document` object to a database-friendly format) with the database insertion logic in a single `_insert_document` method. This made the component harder to test and maintain.

**Action:** I refactored the `SQLiteOutputSink` to separate these concerns, following a strict Test-Driven Development (TDD) process. I first created a new test file and wrote both a locking test to preserve existing behavior and a failing test to drive the refactoring. I then introduced a new `_document_to_record` method dedicated to serializing a `Document` into a simple dictionary. The `_insert_document` method was simplified to accept this dictionary, making it a pure data-insertion function.

**Reflection:** This refactoring is another successful application of the "Data over logic" principle. By separating the "what" (the data record) from the "how" (the SQL insertion), the code becomes cleaner and more modular. The TDD process was essential, not only for ensuring correctness but also for revealing a minor flaw in my initial test setup that was quickly corrected. This pattern of creating dedicated serialization methods can and should be applied to other data sinks in the `infra` layer to promote consistency and maintainability.