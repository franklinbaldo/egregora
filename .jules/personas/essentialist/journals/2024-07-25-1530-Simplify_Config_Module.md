## 💎 2024-07-25 - Simplifying the Core Config
**Observation:** The core configuration module (`src/egregora_v3/core/config.py`) contained several violations of the Essentialist Heuristics.
- The `EgregoraConfig.load` class method was an imperative, custom implementation of configuration loading, violating the "Declarative over imperative" heuristic. It manually read a TOML file and merged settings, reinventing functionality already present in `pydantic-settings`.
- The `PathsSettings` class used multiple `@property` methods (`abs_posts_dir`, `abs_media_dir`, etc.) to resolve absolute paths. This created unnecessary boilerplate and violated the "Explicit over implicit" heuristic by hiding the resolution logic behind properties.

**Action:** I refactored `src/egregora_v3/core/config.py` to align it with Essentialist principles, following a strict Test-Driven Development (TDD) approach.
- I deleted the custom `EgregoraConfig.load` method.
- I refactored `EgregoraConfig` to use `pydantic-settings`'s built-in, declarative TOML loading by adding a `TomlConfigSettingsSource` to the `settings_customise_sources` method. This simplified the code and delegated responsibility to the library.
- I removed the redundant `@property` methods in `PathsSettings` and replaced them with a single, explicit `resolve(path: Path) -> Path` method.
- I created a new test file, `tests/v3/core/test_config.py`, and wrote tests that first captured the old behavior and then verified the new, simplified, and correct implementation.
