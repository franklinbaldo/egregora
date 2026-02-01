# Technical Reference

This section serves as a deep dive into the internal mechanics, command-line interface, and architectural decisions of Egregora.

!!! note "Target Audience"
    This reference is primarily for **Contributors**, **Advanced Users**, and **Developers** who want to understand how Egregora works under the hood or extend its functionality.

## Core References

### 1. CLI Reference
Run `egregora --help` (or `egregora <command> --help`) for detailed documentation of all command-line arguments and flags.
*   `egregora init`: Initialize a new site.
*   `egregora write`: Generate the blog from chat exports.
*   `egregora read`: Read and analyze processed data.

### 2. [Architecture Overview](../v3/architecture/overview.md)
A high-level view of the system's design, including:
*   The **Functional Pipeline** pattern (`Table -> Table` transformations).
*   **Three-Layer Architecture** (Orchestration, Transformations, Primitives).
*   **Data Flow** diagrams explaining how messages travel from ingestion to publication.
*   **Privacy Layer** mechanics.

### 3. [Configuration Reference](../getting-started/configuration.md)
Complete guide to `.egregora.toml` settings (with notes for migrating legacy `config.yml` setups).
*   Model selection and parameters.
*   Pipeline windowing rules.
*   Prompt customization.

### 4. [Database Schema](api/database/schemas.md)
Documentation of the internal Ibis/DuckDB schemas used for:
*   Intermediate Representation (IR).
*   Run tracking.
*   RAG vector storage.

## Key Concepts

*   **Ibis Everywhere:** We use [Ibis](https://ibis-project.org) as the unified dataframe API to abstract SQL complexities and ensure portability.
*   **Privacy-First:** Anonymization happens *within* the input adapter, ensuring no PII leaks into the pipeline or LLM context.
*   **Sync-First:** The core pipeline is synchronous (blocking), using thread pools for parallel I/O, to avoid `asyncio` complexity in data processing steps.

## Developer Resources

*   [Contributing Guide](../community/contributing.md): Coding standards and PR process.
*   [Project Structure](../v3/architecture/layers.md): File organization and module responsibilities.
*   [Testing Strategy](../community/contributing.md#testing): How to run and write tests.
