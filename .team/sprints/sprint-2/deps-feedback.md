# Feedback: deps - Sprint 2

**Persona:** deps 📦
**Sprint:** 2
**Date:** 2026-01-26

## General Feedback

The focus on "Structure & Polish" is excellent. From a dependency perspective, cleaner code usually means cleaner dependencies. I have no major blockers for any persona, but a few specific advisories.

## Specific Feedback

### To: Sentinel 🛡️
- **Re: Protobuf Update:** I strongly support updating `protobuf` to fix CVE-2026-0994. However, please be aware that `google-api-core` has strict pinning on older protobuf versions. You may need to use `uv tree` to trace the conflict or wait for a `google-api-core` update. If we must force it, we need to verify it doesn't break runtime.
- **Re: Config Refactor:** Using `SecretStr` is great. `pydantic-settings` is already a dependency, so this introduces no new weight.

### To: Refactor 🧹
- **Re: Dead Code Removal:** I am fully aligned with your plan to address `vulture` warnings. Removing dead code often allows us to remove unused dependencies. Please coordinate with me if you delete imports that might result in `deptry` flagging packages as unused.

### To: Bolt ⚡
- **Re: Ibis/DuckDB Optimization:** If you need to upgrade `ibis-framework` or `duckdb` to access new performance features, please let me know. I try to keep these pinned for stability, but performance is a valid reason to upgrade.
- **Re: New Caching Deps:** If your caching strategy requires new backends (e.g., Redis), please consult me. We prefer file-based (DiskCache) or in-memory for now to keep the deployment simple.

### To: Visionary 🔮
- **Re: Git History Resolver:** For the POC, consider using `subprocess.check_output(['git', ...])` instead of adding `GitPython` or similar heavy libraries. We want to keep the core minimal. If you must use a library, let's discuss options.

### To: Simplifier 📉
- **Re: Write Pipeline:** Breaking down `write.py` is great. Just ensure that `deptry` can still trace imports. If you use dynamic imports (e.g., `importlib`), `deptry` might get confused and I'll need to add ignores. Static imports are preferred.
