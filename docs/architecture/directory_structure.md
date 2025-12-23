# Directory Structure

This document tracks the directory structure of the Egregora codebase.

## `src/egregora`

*   `agents/`: Logic for AI agents (e.g., writer, banner, enricher).
*   `cli/`: Command-line interface entry points.
*   `config/`: Configuration settings and management.
*   `data_primitives/`: Core data structures (Document, Entry, etc.).
*   `database/`: Database connectivity and schema definitions (DuckDB, Ibis).
*   `infra/`: Infrastructure components.
*   `init/`: Site initialization logic.
*   `input_adapters/`: Adapters for ingesting data (e.g., WhatsApp).
*   `knowledge/`: Knowledge base components (Profiles).
*   `models/`: AI model interfaces and wrappers.
*   `orchestration/`: Pipeline orchestration and execution logic.
    *   `pipelines/`: Specific pipeline implementations (e.g., `write`).
        *   `modules/`: Shared modules used by pipelines.
            *   `media.py`: Media handling operations.
            *   `taxonomy.py`: Taxonomy generation logic.
*   `output_adapters/`: Adapters for outputting data (e.g., MkDocs).
*   `privacy/`: Privacy handling components.
*   `prompts/`: Prompt management.
*   `rag/`: Retrieval-Augmented Generation components.
*   `rendering/`: Template rendering.
*   `resources/`: Static resources (SQL, prompts).
*   `templates/`: Jinja2 templates.
*   `transformations/`: Functional data transformations.
*   `utils/`: Utility functions.
