# Revised Lint Fix Plan for Egregora

## 1. Automated Fixes
Run `ruff check --fix` to handle:
- `I001` (Unsorted imports)
- `F401` (Unused imports)
- `W292` (Missing newline)
- `TC005` (Empty type checking block)
- `F811` (Redefinition)

## 2. Standardizing File Operations (`PTH123`)
Convert `open(path)` to `path.open()` or `Path(path).open()`.

## 3. Exception Handling Strategy (`S110`, `BLE001`, `TRY...`)
**Strict Rule:** No silent failure.
- **`S110` (try-except-pass):**
  - **Option A (Preferred):** Remove the try/except and let the error propagate if the caller can handle it.
  - **Option B:** Catch specific exception (e.g., `FileNotFoundError`) and use `logger.warning` or `logger.exception`.
- **`TRY401` (Redundant logging):** Remove `exception` arg from `logger.exception`.

## 4. Import Cleanup (`PLC0415`)
- Avoid inline imports.
- **Strategy:**
  - Move to top-level where possible.
  - If avoiding circular dependencies or heavy load: Use `importlib.import_module()` for dynamic loading instead of raw import statements inside functions.

## 5. Global State Refactoring (`PLW0603`)
**Target:** `rate_limit.py` (`_limiter`) and `embedding_router.py` (`_router`).
- **Goal:** Remove global singletons.
- **Refactoring:**
  1.  Modify the Context/Configuration object to hold these instances.
  2.  Initialize them in `main.py` or the application entry point.
  3.  Pass them down via function arguments (`dependency injection`) to where they are needed.

## 6. Code Complexity (`C901`, `PLR...`)
- Refactor large functions into smaller, testable units.
- Avoid `noqa` unless absolutely necessary (e.g., legacy interface compliance).

## Execution Order
1.  **Basics:** Automated fixes & Pathlib conversion.
2.  **Safety:** Fix silent exceptions (`S110`).
3.  **Architecture:** Refactor Global State (Rate Limiter & Router).
4.  **Cleanup:** Imports & Complexity.
