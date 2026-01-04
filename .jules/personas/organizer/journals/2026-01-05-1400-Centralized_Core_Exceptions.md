---
title: "🗂️ Centralized Core Application Exceptions"
date: 2026-01-05
author: "Organizer"
emoji: "🗂️"
type: journal
---

## 🗂️ 2026-01-05 - Summary

**Observation:** The application's base exception, `EgregoraError`, and its related subclasses were defined in a generic utility module, `src/egregora/utils/text.py`. This violated the Single Responsibility Principle, as a core architectural component was hidden in an unrelated module, making the error hierarchy difficult to discover and maintain.

**Action:**
- Created a new, dedicated module for core exceptions at `src/egregora/core/exceptions.py`.
- Moved the `EgregoraError`, `SlugifyError`, and `InvalidInputError` classes from `utils/text.py` to the new `core/exceptions.py` module.
- Updated all consumer imports across the codebase to point to the new, centralized location.
- Added a docstring to the new `core` package and fixed an import order issue in `utils/text.py` to satisfy pre-commit checks.

**Reflection:** This refactoring successfully centralized the application's core exception hierarchy, improving the logical structure and making the code easier to navigate. The `utils` directory is now cleaner, but it should be systematically reviewed for other misplaced domain-specific logic. The pre-commit failures highlight the importance of adhering to the project's coding standards during refactoring. The next session should continue the audit of the `utils` directory.
