---
title: "💎 Refactor DuckDB Repo for Hydration Simplicity"
date: 2025-12-24
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-24 - Simplify DuckDB Repository Hydration
**Observation:** The `DuckDBDocumentRepository` in `src/egregora_v3/infra/repository/duckdb.py` contained duplicated object hydration logic across multiple data retrieval methods (`get`, `list`, `get_entry`, and `get_entries_by_source`). This violated the "Don't Repeat Yourself" (DRY) principle and the "Small modules over clever modules" heuristic by scattering imperative JSON parsing and type-checking logic, making the module difficult to maintain.

**Action:** I refactored the repository to centralize the object creation logic. I introduced a private `_hydrate_object` method that handles the deserialization of a JSON row into either an `Entry` or a `Document` based on its `doc_type`. All data retrieval methods were then simplified to call this single helper function, removing significant code duplication. I also simplified the `get_entries_by_source` method to use a single, reliable raw SQL query, removing the complex and unnecessary fallback logic. The entire process was guided by Test-Driven Development (TDD), starting with a new test to lock in the correct behavior before refactoring.