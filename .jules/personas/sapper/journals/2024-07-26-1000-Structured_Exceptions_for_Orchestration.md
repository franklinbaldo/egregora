---
title: "💣 Structured Exceptions for Orchestration"
date: 2024-07-26
author: "Sapper"
emoji: "💣"
type: journal
---

## 💣 2024-07-26 - Summary

**Observation:** The `egregora.orchestration.runner` module was a minefield of implicit failure modes. It relied heavily on generic `RuntimeError` and `ValueError` exceptions, and multiple `except Exception` blocks silently swallowed critical errors, violating the "Trigger, Don't Confirm" principle. This made the core pipeline logic fragile and difficult to debug.

**Action:** I executed a full TDD-based refactoring of the module's exception handling.
1.  **Established Hierarchy:** Created a new `src/egregora/orchestration/exceptions.py` module with a base `OrchestrationError` and specific, context-rich exceptions like `WindowValidationError`, `MaxSplitDepthError`, `OutputSinkError`, `MediaPersistenceError`, `CommandProcessingError`, and `ProfileGenerationError`.
2.  **TDD Refactoring:** For each of the identified weak points in `runner.py`, I wrote a failing test to prove the defect, then refactored the code to raise the new, specific exception, ensuring the test passed. This covered validation logic, recursion depth limits, and error handling during media persistence, command processing, and profile generation.
3.  **Code Cleanup:** Ran the full pre-commit suite, fixing all linting errors, including unused variables and incorrect pytest fixture usage, to ensure the code adheres to project standards.

**Reflection:** This was a highly successful operation. The `PipelineRunner` is now significantly more robust, with explicit, informative, and test-verified failure modes. The next logical target for reconnaissance is the `egregora.input_adapters` module. These adapters are the system's first point of contact with external data, making them critical boundaries where structured exception handling is paramount to prevent bad data from corrupting the pipeline. I'll be looking for any signs of LBYL checks or generic exceptions when parsing and processing input files.
