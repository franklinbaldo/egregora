---
title: "Refactor Demo Generation to use Offline Cache"
id: "refactor-demo-cache"
enabled: true
schedule: ""
branch: "claude/reconcile-pr-1371-0ga0G"
automation_mode: "AUTO_COMMIT"
require_plan_approval: true
---

# Tasks

Implement a robust offline demo generation strategy by leveraging `diskcache` instead of extensive mocking.

## Objectives

1. **Refactor `scripts/generate_demo_site.py`**:
    - Remove the extensive patching of agents (`_patch_pipeline_for_offline_demo`).
    - Keep necessary patches (e.g., `is_banner_generation_available` force-false if banners are overkill for demo).
    - Configure `EgregoraConfig` to use a committed cache directory: `docs/demo/.egregora/cache`.

2. **Generate Cache Artifacts**:
    - Run the generation once with a valid API key (using `uv run egregious write ...`).
    - Ensure the cache is populated in `docs/demo/.egregora/cache`.
    - Commit the cache to the repo (ensure `.gitignore` allows it for this specific path).

3. **Update Config**:
    - Ensure `docs/demo/.egregora/config.yml` (or `.toml`) points to this cache directory.
    - Verify that when running *without* an API key but *with* the cache, the generation succeeds.

## Implementation Details

- `src/egregora/utils/cache.py` defines the backend.
- Ensure `diskcache` version compatibility.
- Add `docs/demo/.egregora/cache` to git.

## Definition of Done

- `scripts/generate_demo_site.py` is simplified.
- `docs/demo/.egregora/cache` exists and is populated.
- Demo site builds successfully in offline mode (unset `GOOGLE_API_KEY`/`GEMINI_API_KEY` to verify).
