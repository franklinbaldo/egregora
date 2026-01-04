---
title: "🗂️ Co-located Chunking Logic with RAG Module"
date: 2026-01-05
author: "Organizer"
emoji: "🗂️"
type: journal
---

## 🗂️ 2026-01-05 - Summary

**Observation:** The `src/egregora/text_processing` directory contained a single module, `chunking.py`, whose functionality was exclusively used by the Retrieval-Augmented Generation (RAG) components. This violated the principle of co-location and created an unnecessary, single-file directory.

**Action:**
1.  Moved `src/egregora/text_processing/chunking.py` to `src/egregora/rag/chunking.py`.
2.  Moved the corresponding test file from `tests/unit/text_processing/` to `tests/unit/rag/`.
3.  Updated all consumer imports in `src/egregora/rag/ingestion.py` and `src/egregora_v3/infra/rag.py` to point to the new location.
4.  Updated the import in the test file itself, which was missed initially and caught by the test runner.
5.  Deleted the now-empty `src/egregora/text_processing` and `tests/unit/text_processing` directories.
6.  Updated the `docs/organization-plan.md` to reflect this completed improvement and restore the historical log of changes.

**Reflection:** This was a successful and low-risk refactoring that improves the codebase's logical structure by placing domain-specific logic where it belongs. The initial test failure due to a missed import update in the test file itself reinforces the importance of running tests after every structural change. Generic utility directories are often a code smell, and they should be a primary target for future organizational improvements.
