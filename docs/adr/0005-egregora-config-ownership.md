# 5. Egregora Configuration Ownership

Date: 2025-12-17

## Status

Accepted

## Context

There is potential confusion regarding the relationship between the Egregora-specific configuration (`.egregora.toml`, `.egregora/` directory) and the `MkDocsOutputAdapter`. Questions arise about whether the adapter is responsible for managing these files, creating them, or if they are strictly required for the adapter to function.

## Decision

1.  **Optional Helper Instruments**: The `.egregora.toml` file and the `.egregora/` directory are defined as **optional helper instruments** for easier setting management.
    *   They serve as a persistent store for user preferences (source type, model selection, step size, path overrides).
    *   They allow the Egregora CLI and Pipeline to function with fewer repeated arguments.

2.  **Not Managed by Output Adapter**: The `MkDocsOutputAdapter` is **not** responsible for the lifecycle (creation, updates, maintenance) of these configuration artifacts.
    *   **Role of Adapter**: The Adapter's sole responsibility is to **render content** (posts, media, profiles) into the filesystem structure. It *consumes* the configuration to know *where* to write, but it does not *manage* the configuration file itself.
    *   **Role of CLI/Init**: The logic for standardizing, creating, and updating `.egregora.toml` belongs to the Egregora CLI (`egregora init`) and high-level orchestration, not the output rendering layer.

3.  **Config Over Code**: The Adapter must strictly adhere to the paths resolved from the configuration (as implemented in `MkDocsPaths`), but it should treat the configuration source as opaque. Whether the config comes from `.egregora.toml`, environment variables, or hardcoded defaults is a concern for the *config loader*, not the *output adapter*.

## Consequences

*   **Logic Separation**: We will avoid adding logic to `MkDocsOutputAdapter` that modifies `config.toml` or prompts for configuration values.
*   **Portability**: The Output Adapter remains focused on the MkDocs specification (generating Markdown and YAML), making it easier to swap or upgrade without entangling it in Egregora-specific state management.
*   **Flexibility**: Users may theoretically use the Egregora pipeline without a config file if all parameters are supplied via CLI or objects, ensuring the system remains composable.
