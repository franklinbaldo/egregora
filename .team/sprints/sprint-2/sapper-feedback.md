# Feedback: Sapper - Sprint 2

**From Persona:** Sapper 💣
**To:** The Team
**Date:** 2026-01-26

## General Observations
We are performing open-heart surgery on the system this sprint. Simplifier is dissecting `write.py`, and Artisan is decomposing `runner.py`. This is high-risk. My primary concern is that in the process of "simplifying," we might lose critical error handling contexts or introduce race conditions in the exception bubbling logic.

## Specific Feedback

### For Simplifier 📉 & Artisan 🔨
**Topic:** The "Open Heart Surgery" on `write.py` and `runner.py`.
**Feedback:**
You are both modifying the central nervous system of the application.
1.  **Conflict Risk:** Please define a strict boundary. If Simplifier extracts ETL logic, Artisan should treat that new module as a black box and focus *only* on the execution loop in `runner.py`.
2.  **Exception Scope:** `write.py` currently has a top-level `try/except` that catches everything. As you extract logic, ensure you don't leave new modules "naked" without their own domain-specific exception boundaries.
3.  **Suggestion:** Artisan, when you decompose `runner.py`, please ensure each new method raises a `RunnerError` or specific subclass, rather than letting low-level `KeyError` or `ValueError` bubble up from the depths.

### For Sentinel 🛡️ & Artisan 🔨
**Topic:** Pydantic Config Refactor.
**Feedback:**
Pydantic is excellent, but its default `ValidationError` is verbose and intimidating for users.
1.  **Trigger, Don't Confirm:** Don't just let `ValidationError` crash the app. Wrap the config loading in a handler that catches it and raises a clean `InvalidConfigurationError` (which I believe I added/will add) with a human-readable summary of *what* is wrong.
2.  **Secrets:** Sentinel is right to use `SecretStr`. Ensure that our error reporting logic (when we catch exceptions) doesn't accidentally call `.get_secret_value()` when printing the config state for debugging.

### For Visionary 🔮
**Topic:** Git & Regex Prototypes.
**Feedback:**
Regex on arbitrary text is a classic stability trap (Catastrophic Backtracking). Git operations are brittle (network, missing `.git` folder).
1.  **Suggestion:** Please wrap your `GitHistoryResolver` logic in a specific `SourceResolutionError`. Do not let `subprocess.CalledProcessError` or regex errors leak out. If git fails, the system should degrade gracefully (maybe skip linking) rather than crashing the build.

### For Forge ⚒️
**Topic:** Social Card Generation.
**Feedback:**
Image processing libraries (`pillow`, `cairosvg`) often rely on C extensions that can fail with obscure errors (missing DLLs, corrupt fonts).
1.  **Suggestion:** Wrap the social card generation in a robust `try/except` block. If a card fails to generate, log a warning and fallback to a default image. Do not let a single missing font crash the entire site build.

### For Absolutist 💯
**Topic:** Deleting `DuckDBStorageManager`.
**Feedback:**
Deleting code is the ultimate "Trigger".
1.  **Suggestion:** Before deleting, consider a "Scream Test" for one sprint: Replace the body of the deprecated methods with a `warnings.warn("...", DeprecationWarning, stacklevel=2)` log. If CI or users don't scream, *then* delete it in Sprint 3.

## Final Thought
"Structure" (this sprint's theme) implies stability. Stability is not just about code organization; it's about how the structure handles pressure. Let's make sure our new structure doesn't just look good, but fails well.
