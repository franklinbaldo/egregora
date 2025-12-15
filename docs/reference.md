# Technical Reference

This section serves as a deep dive into the internal mechanics, command-line interface, and architectural decisions of Egregora.

!!! note "Target Audience"
    This reference is primarily for **Contributors**, **Advanced Users**, and **Developers** who want to understand how Egregora works under the hood or extend its functionality.

## Core References

### 1. [CLI Reference](api/orchestration/cli.md)
Detailed documentation of all command-line arguments, environment variables, and subcommands.
*   `egregora init`: Site scaffolding internals.
*   `egregora write`: Pipeline execution flags and caching strategies.
*   `egregora read`: Ranking and evaluation commands.

### 2. [Architecture Overview](guide/architecture.md)
A high-level view of the system's design, including:
*   The **Functional Pipeline** pattern (`Table -> Table` transformations).
*   **Three-Layer Architecture** (Orchestration, Transformations, Primitives).
*   **Data Flow** diagrams explaining how messages travel from ingestion to publication.
*   **Privacy Layer** mechanics.

### 3. [Configuration Reference](getting-started/configuration.md)
Complete guide to `egregora.toml` and `config.yml` settings.
*   Model selection and parameters.
*   Pipeline windowing rules.
*   Prompt customization.

### 4. [Database Schema](api/core/schema.md)
Documentation of the internal Ibis/DuckDB schemas used for:
*   Intermediate Representation (IR).
*   Run tracking.
*   RAG vector storage.

## Key Concepts

*   **Ibis Everywhere:** We use [Ibis](https://ibis-project.org) as the unified dataframe API to abstract SQL complexities and ensure portability.
*   **Privacy-First:** Anonymization happens *within* the input adapter, ensuring no PII leaks into the pipeline or LLM context.
*   **Sync-First:** The core pipeline is synchronous (blocking), using thread pools for parallel I/O, to avoid `asyncio` complexity in data processing steps.

## Developer Resources

*   [Contributing Guide](development/contributing.md): Coding standards and PR process.
*   [Project Structure](development/structure.md): File organization and module responsibilities.
*   [Testing Strategy](development/testing.md): How to run and write tests.
