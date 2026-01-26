# Feedback: Sentinel 🛡️

## General Observations
Sprint 2 is a critical structural phase. Breaking down `write.py` and `runner.py` while introducing Pydantic for configuration is necessary, but it introduces significant transient risks. We must ensure security contexts (rate limits, blocklists, secret handling) are not lost in the refactor.

## Persona-Specific Feedback

### To Visionary 🔭
**Plan:** `GitHistoryResolver` Prototype
**Risk:** High (Command Injection)
**Feedback:**
The `GitHistoryResolver` appears to take user input (timestamps, file paths) and potentially pass them to the Git CLI. This is a classic vector for Command Injection.
**Requirement:**
- Please ensure strict input validation (allow-lists for characters in file paths).
- Use `subprocess.run` with `shell=False` and list arguments, NEVER `shell=True`.
- Consult me for a review of the `resolve_commit.py` script before merging.

### To Artisan 🔨
**Plan:** Config Refactor & Runner Decomposition
**Risk:** High (Secret Leakage)
**Feedback:**
Moving `config.py` to Pydantic is a great move for type safety, but it poses a risk of accidentally printing secrets in logs if the `__repr__` isn't handled correctly.
**Requirement:**
- You MUST use `pydantic.SecretStr` for any field containing keys (API keys, tokens).
- Ensure that the new `PipelineRunner` explicitly propagates the "Context" object (which holds the security state) to all decomposed methods.

### To Forge ⚒️
**Plan:** Social Cards (Pillow/CairoSVG)
**Risk:** Medium (Dependency Vulnerabilities)
**Feedback:**
Image processing libraries are frequent targets for vulnerabilities.
**Requirement:**
- Please ensure you are pinning the versions of `pillow` and `cairosvg`.
- Be aware that `pillow` has frequent security updates; checking for updates should be part of the task.

### To Simplifier 📉
**Plan:** `write.py` decomposition
**Risk:** Medium (Bypassing Checks)
**Feedback:**
When extracting the ETL pipeline, ensure that the input validation steps (e.g., checks on the input file format/path) happen *before* any processing begins. Do not "simplify" away the safety checks.
