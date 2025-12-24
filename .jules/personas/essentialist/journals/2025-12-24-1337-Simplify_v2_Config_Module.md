---
title: "💎 Simplifying the v2 Core Config"
date: 2025-12-24
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-24 - Simplifying the v2 Core Config
**Observation:** The v2 configuration module (`src/egregora/config/settings.py`) contained several violations of the Essentialist Heuristics. The configuration loading was imperative and complex, a clear violation of the "Declarative over imperative" heuristic. It reinvented the wheel instead of using `pydantic-settings` features. The module was also bloated with too many responsibilities.

**Action:** I refactored `src/egregora/config/settings.py` to align it with Essentialist principles, following a strict Test-Driven Development (TDD) approach. I refactored `EgregoraConfig` to use `pydantic-settings`'s built-in, declarative TOML loading by adding a `TomlConfigSettingsSource` to the `settings_customise_sources` method. I then removed the now-redundant `load_egregora_config`, `find_egregora_config`, `_merge_config`, `_collect_env_override_paths`, and `_normalize_sites_config` functions. Finally, I updated all call sites to use the new, simpler instantiation pattern and fixed the tests that broke as a result of the refactoring.
