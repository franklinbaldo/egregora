# API Reference

Complete API documentation for all Egregora modules, automatically generated from source code docstrings.

## Overview

Egregora is organized into functional modules following the staged pipeline architecture:

```
egregora/
├── ingestion/       # Parse WhatsApp exports
├── privacy/         # Anonymization & PII detection
├── augmentation/    # Enrichment & profiling
├── knowledge/       # RAG, annotations, rankings
├── generation/      # LLM writer & editor
├── publication/     # Site scaffolding
├── core/            # Shared models & schemas
├── orchestration/   # CLI & pipeline coordination
├── config/          # Configuration management
└── utils/           # Batch processing, caching
```

## Quick Navigation

### Pipeline Stages

| Module | Description |
|--------|-------------|
| [Ingestion](ingestion/parser.md) | Parse WhatsApp exports |
| [Privacy](privacy/anonymizer.md) | Anonymization & PII detection |
| [Augmentation](augmentation/enrichment.md) | Enrich context with LLMs |
| [Knowledge](knowledge/rag.md) | RAG, annotations, rankings |
| [Generation](generation/writer.md) | Content generation |
| [Publication](publication/scaffolding.md) | Site creation |

### Core Modules

| Module | Description |
|--------|-------------|
| [Schema](core/schema.md) | Database schemas |
| [Models](core/models.md) | Pydantic models |
| [Types](core/types.md) | Type definitions |

### Orchestration

| Module | Description |
|--------|-------------|
| [Pipeline](orchestration/pipeline.md) | End-to-end workflow |
| [CLI](orchestration/cli.md) | Command-line interface |

## Using the API Documentation

Each module's documentation is **automatically generated** from the source code docstrings. Click on any module above to see:

- All public functions and classes
- Parameter types and descriptions
- Return values
- Usage examples from docstrings
- Source code

## Common Patterns

### DataFrame Transformations

All data flows through Ibis DataFrames. See individual module documentation for specific functions and their signatures.

### Batch Processing

The `utils.batch` module provides utilities for processing large datasets efficiently.

### Caching

The `utils.cache` module provides disk-based caching for expensive operations.

## Type Hints

Egregora uses type hints throughout. Check the [Types](core/types.md) module for custom type definitions and the individual module pages for function signatures.

## Next Steps

- Browse the module documentation in the sidebar
- See [User Guide](../guide/architecture.md) for conceptual overview
- Check [Development Guide](../development/contributing.md) for contributing
