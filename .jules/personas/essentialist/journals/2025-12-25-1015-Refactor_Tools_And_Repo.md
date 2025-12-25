---
title: "💎 Refactor Tools and Repository for Data-Driven Logic"
date: "2025-12-25"
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-25 - Pushing Logic to the Database
**Observation:** The `get_recent_posts` tool in `src/egregora_v3/engine/tools.py` was fetching all post documents from the repository and then performing sorting and limiting operations in application memory. This is a clear violation of the "Data over logic" heuristic, as it is inefficient and mixes data retrieval with data processing logic.

**Action:** I refactored the codebase to delegate this logic to the database.
1.  I extended the `list` method in the `DuckDBDocumentRepository` to accept `order_by` and `limit` parameters, which are then used to construct a more efficient Ibis query.
2.  I simplified the `get_recent_posts` tool to be a single, declarative call to the updated repository method.
3.  I followed a strict Test-Driven Development (TDD) process throughout. This was crucial, as it helped me identify and correct several mistakes along the way.

**Reflection:** This task was a powerful reminder of the importance of rigorous TDD and ensuring that test coverage follows the logic. My initial refactoring was correct, but my testing was flawed:
1.  I initially deleted existing tests for other tools, which was a major error caught by the code review.
2.  I then failed to create a new integration test for the repository logic I had moved, which was also caught in review.

The final solution is a model of the "Data over logic" principle. The tool is simple and declarative, and the database does the heavy lifting. The test suite is now more robust, with focused unit tests for the tools and a new integration test for the repository. This experience reinforces the idea that when you move code, you must move the tests (or write new ones) with it.
