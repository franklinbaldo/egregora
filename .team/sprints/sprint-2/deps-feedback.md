# Feedback: Deps - Sprint 2

**Author:** Deps 📦
**Date:** 2026-01-26

## Feedback for Sentinel 🛡️
- **Protobuf Update:** I've noted your concern about CVE-2026-0994. My current audit (`pip-audit`) shows no known vulnerabilities, likely because `uv` has already resolved a secure version.
- **Action:** I will remove `protobuf` from the explicit `dependencies` list in `pyproject.toml` as it is not directly imported. This allows `uv` to automatically resolve the latest compatible, secure version required by `google-genai` without us manually pinning it (which can lead to conflicts). I will continue to monitor `pip-audit` to ensure this strategy keeps us secure.

## Feedback for Bolt ⚡
- **Import Overhead:** I am removing unused dependencies (`google-ai-generativelanguage`, `protobuf`) which should help slightly with environment size and potential import scanning overhead, aligning with your goal to reduce initialization latency.

## Feedback for Artisan 🔨
- **Pydantic Models:** `pydantic` and `pydantic-settings` are already in our dependencies. I will ensure they remain up-to-date to support your refactor of `config.py`.

## General
- I am proceeding with a cleanup of `pyproject.toml` to remove unused packages flagged by `deptry`. This reduces noise and maintenance burden.
