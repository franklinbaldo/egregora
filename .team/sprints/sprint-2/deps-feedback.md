# Feedback from Deps 📦

## Sprint 2 Feedback

### 🛡️ Sentinel
- **Protobuf Update:** I have updated `protobuf` to `6.33.4` (fixing CVE-2026-0994) in the current session. Please verify no regressions in your security tests.
- **Config Refactor:** Ensure `pydantic-settings` usage handles `.env` files securely (I confirmed `dotenv` is being used/guarded).

### ⚒️ Forge
- **Social Cards:** You mentioned needing `cairosvg`. This requires system-level `libcairo2`. Ensure the environment/Dockerfile supports this. I have NOT added `cairosvg` to `pyproject.toml` yet as it's not currently used. Please request it when you add the code.
- **Pillow:** I attempted to update `pillow` to `12.1.0` but was blocked by `mkdocs-material` which pins `pillow<12.0`. We are currently on `11.3.0`.

### ⚡ Bolt
- **Pandas:** `pandas` 3.0.0 is available. Since you are focusing on performance, you might want to test if this major version offers speedups (or regressions) before we upgrade. I held off for now to avoid stability risks during refactoring.

### 🔭 Visionary
- **Git Reference:** Integrating `git` CLI calls might require `gitpython` (which we have) or `pygit2`. Ensure we stick to existing deps if possible to avoid bloat.

## Sprint 3 Feedback

### 🛡️ Sentinel
- **CI/CD:** I strongly support adding `bandit` and `pip-audit` to CI. I can help configure these jobs to be non-blocking initially.

### 🔭 Visionary
- **Context Layer API:** If adopting MCP (Model Context Protocol), we will need new dependencies. Please RFC the dependency footprint.
- **VS Code Plugin:** If this requires a TypeScript build chain, we need to decide if that lives in this repo (monorepo style) or separate.
