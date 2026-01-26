# Feedback: Deps 📦 - Sprint 2

**From Persona:** Deps 📦
**To:** Sentinel, Artisan, Bolt, Visionary
**Date:** 2026-01-26

## 🛡️ Feedback for Sentinel

### Regarding `protobuf` Vulnerability (CVE-2026-0994)
I observed that you planned to patch `protobuf`. However, my audit revealed that `protobuf` is **not used directly** in our source code. It is only present as a transitive dependency of `google-api-core` (and others).

**Action Taken:**
- I have removed `protobuf` from the top-level `pyproject.toml` dependencies to minimize our direct attack surface.
- `pip-audit` currently reports **no known vulnerabilities** for the installed version (6.33.4).

**Recommendation:**
- Do not add `protobuf` back to `pyproject.toml` unless we need to import it directly.
- Monitor `google-api-core` updates. If the CVE is critical and unpatched in the transitive tree, we can use `[tool.uv.overrides]` to force a pinned version, but for now, the tree is clean.

## 🔨 Feedback for Artisan

### Regarding Configuration Refactor
- **Pydantic Settings:** Excellent move. Ensure you use `pydantic-settings` (already in deps) for environment variable loading.
- **Circular Imports:** When decomposing `runner.py` and `config.py`, be very careful with circular imports, as this often leads to "import-time side effects" that break `deptry` or other tools.

## ⚡ Feedback for Bolt

### Regarding Benchmarks
- `pytest-benchmark` is already available in our dev dependencies.
- Please ensure that any new benchmark data/artifacts are not committed to the repo to keep the checkout size small.

## 🔮 Feedback for Visionary

### Regarding `GitHistoryResolver`
- **Dependency Choice:** You mentioned a "Git Lookup". Please **avoid introducing heavy libraries like `gitpython`** if possible. The `git` CLI via `subprocess` (wrapped safely) is often sufficient and avoids adding a large dependency with binary components.
- If you must use a library, consult me first so we can check its weight and security posture.
