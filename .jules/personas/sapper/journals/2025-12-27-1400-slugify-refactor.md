---
title: "💣 Structured Exceptions for Slugify Utility"
date: 2025-12-27
author: "Sapper"
emoji: "💣"
type: journal
---

## 💣 2025-12-27 - Summary

**Observation:** The `slugify` utility, duplicated in both the `v2` and `v3` codebases, was a classic "Look Before You Leap" (LBYL) violation. It returned an empty string for `None` input, hiding errors and creating the potential for downstream bugs. My mission was to refactor this to raise a structured exception.

**Action:** The mission was executed in multiple, painful phases due to a series of critical errors on my part.
1.  **Initial Refactoring:** I correctly identified the target, created a new `InvalidInputError`, and modified the `v2` `slugify` to raise it.
2.  **CRITICAL ERROR 1:** My first code review revealed I had failed to update any of the call sites, leaving the application in a broken state.
3.  **Corrective Action & CRITICAL ERROR 2:** I then attempted to fix the call sites, but in doing so, I discovered a duplicated `slugify` function in the `v3` codebase. I refactored both, but created a *second*, duplicated `InvalidInputError` and used inconsistent handling strategies (EAFP, LBYL, and `str()` casting) across the call sites. This was a catastrophic failure of discipline.
4.  **Final, Correct Refactoring:** After a second, brutal code review, I executed the mission correctly.
    *   **Consolidated:** I deleted the duplicated `slugify` and `InvalidInputError`, establishing a single source of truth for both.
    *   **Consistent EAFP:** I revisited every single call site and applied a consistent `try...except InvalidInputError` strategy, removing all other forms of error handling.
    *   **Cleaned:** I removed redundant `__init__` methods from the exception class.

**Reflection:** This mission was a powerful, humbling lesson in the importance of discipline, consistency, and thoroughness. My initial failures were a direct result of tunnel vision and a lack of architectural awareness. A Sapper cannot just defuse one bomb; he must understand how the entire system is wired. The key takeaways are:
1.  **Always Address Duplication:** Never propagate a fix to duplicated code. Consolidate first.
2.  **One Problem, One Protocol:** When changing a function's contract, apply one, and only one, consistent error-handling strategy to all call sites. In my case, that is always EAFP.
3.  **The Blast Radius is Always Wider Than You Think:** A change to a utility function has far-reaching consequences. Every single call site must be treated as a potential secondary explosive.

This mission was a failure of execution, but a success in learning. I will not make these mistakes again.
