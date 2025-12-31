# ADR-0004: Configuration Consolidation and TOML Adoption

## Status
Accepted

## Context
The previous configuration system in Egregora V3 was fragmented across multiple modules (`settings.py`, `overrides.py`, `config_validation.py`), leading to maintenance overhead and unclear precedence rules. Configuration was stored in a YAML file (`.egregora/config.yml`) inside a hidden directory, which made it less visible and susceptible to YAML's parsing ambiguities (e.g., the "Norway problem"). Additionally, the loading logic was over-engineered with intermediate builder classes that complicated simple overrides.

There was also a tendency to have "magic" configuration values that were calculated or mutated based on other settings during validation, leading to hidden behaviors and confusion about what the actual configuration state was.

## Decision
We have decided to refactor the configuration system with the following changes:

1.  **Consolidation**: All configuration logic, including loading, saving, and validation, is consolidated into a single module: `src/egregora/config/settings.py`. Intermediate layers like `overrides.py` and `config_validation.py` are removed.
2.  **TOML Adoption**: We are switching the configuration format from YAML to TOML. TOML is the standard for Python configuration (`pyproject.toml`), offers unambiguous type parsing (especially for dates/times), and has native support in Python 3.11+ via `tomllib`.
3.  **Root-Level Config**: The configuration file is moved from `.egregora/config.yml` to `.egregora.toml` in the site root. This improves visibility and aligns with standard tooling conventions.
4.  **Artifact Location**: A new setting `paths.egregora_dir` (defaulting to `.egregora`) is introduced to explicitly define where internal artifacts (RAG database, cache, etc.) are stored, separating configuration from data.
5.  **Strict Precedence**: Configuration loading now follows a strict, predictable precedence order:
    1.  **CLI Arguments** (Highest priority, runtime overrides)
    2.  **Environment Variables** (`EGREGORA_*`)
    3.  **Config File** (`.egregora.toml`)
    4.  **Defaults** (Lowest priority)
6.  **Defined, Not Calculated**: Configuration settings must be explicit ("Defined") rather than dynamically inferred or mutated based on other settings ("Calculated").
    *   **No Magic Defaults**: Defaults must be static, explicit values.
    *   **No Inter-Field Mutation**: Validators must not change the value of field A based on the value of field B (e.g., changing `rag_dir` because `egregora_dir` changed).
    *   **Explicit Relationships**: If a setting conceptually depends on another (e.g., a path inside a directory), it should default to the full relative path explicitly (e.g., `.egregora/rag`). If the user changes the parent directory, they are responsible for updating the child paths if they want them to remain nested. This prioritizes clarity and predictability over magic convenience.

## Consequences
**Positive:**
*   **Reduced Complexity**: A single source of truth for configuration makes the codebase easier to navigate and maintain.
*   **Type Safety**: Leveraging Pydantic for all validation ensures configuration integrity at load time.
*   **Standardization**: TOML provides a more robust and Python-native configuration format.
*   **Predictability**: "Defined, Not Calculated" ensures that the configuration object exactly matches what is in the file/env/defaults, making debugging easier.
*   **Flexibility**: Explicit artifact path configuration allows for better integration with different deployment environments.

**Negative:**
*   **Breaking Change**: Existing sites using `config.yml` will need to migrate to `.egregora.toml`. Support for `config.yml` has been removed to simplify the codebase and avoid ambiguity.
*   **Verbosity**: Users might need to configure multiple paths explicitly if they want to move the entire `.egregora` directory structure to a custom location, rather than changing one setting and having others follow magically.
*   **Python Version Requirement**: The use of `tomllib` requires Python 3.11+, which aligns with the project's requirement of Python 3.12+, but technically raises the minimum bar for the config module itself if extracted.
