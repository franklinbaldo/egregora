# Exceptions Reference

Egregora defines custom exceptions across different modules to provide clear error handling and diagnostics.

## Overview

All exceptions inherit from standard Python exceptions and provide detailed error messages with context. Most modules define a base exception class (e.g., `ConfigError`, `WhatsAppParseError`) from which specific exceptions inherit.

## Configuration Exceptions

Exceptions related to configuration loading, validation, and site management.

::: egregora.config.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Input Adapter Exceptions

### WhatsApp Adapter Exceptions

Exceptions specific to WhatsApp export parsing and processing.

::: egregora.input_adapters.whatsapp.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Agent Exceptions

Exceptions raised during agent execution (writer, reader, enricher agents).

::: egregora.agents.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Pipeline Orchestration Exceptions

Exceptions related to pipeline execution and coordination.

::: egregora.orchestration.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Transformation Exceptions

Exceptions raised during message windowing, enrichment, and transformation.

::: egregora.transformations.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Initialization Exceptions

Exceptions raised during site initialization and MkDocs project setup.

::: egregora.init.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Database Exceptions

Exceptions related to DuckDB storage, ELO store, and database operations.

::: egregora.database.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Utility Exceptions

General utility exceptions used across the codebase.

::: egregora.utils.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Output Adapter Exceptions

Exceptions raised during output generation (MkDocs, static site).

::: egregora.output_adapters.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## LLM Exceptions

Exceptions related to language model interactions and API calls.

::: egregora.llm.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Knowledge/RAG Exceptions

Exceptions related to vector stores, RAG operations, and knowledge retrieval.

::: egregora.knowledge.exceptions
    options:
      show_source: true
      show_root_heading: false
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Exception Hierarchy

Most Egregora exceptions follow this pattern:

```
Exception (Python built-in)
├── ConfigError (base for config exceptions)
│   ├── ConfigNotFoundError
│   ├── ConfigValidationError
│   ├── SiteNotFoundError
│   └── ...
├── WhatsAppParseError (base for WhatsApp exceptions)
│   ├── MessageParseError
│   ├── MediaParseError
│   └── ...
└── ... (other module-specific base exceptions)
```

## Common Usage Patterns

### Catching Specific Exceptions

```python
from egregora.config import load_egregora_config
from egregora.config.exceptions import ConfigNotFoundError, ConfigValidationError

try:
    config = load_egregora_config(Path("./my-site"))
except ConfigNotFoundError as e:
    print(f"Config not found: {e.search_path}")
except ConfigValidationError as e:
    print(f"Config invalid: {e.errors}")
```

### Catching All Exceptions from a Module

```python
from egregora.config.exceptions import ConfigError

try:
    # ... configuration operations
    pass
except ConfigError:
    # Catches ConfigNotFoundError, ConfigValidationError, etc.
    print("A configuration error occurred")
```

### Exception Context

Most exceptions provide additional context via attributes:

```python
from egregora.input_adapters.whatsapp.exceptions import MessageParseError

try:
    # ... parse WhatsApp message
    pass
except MessageParseError as e:
    print(f"Line number: {e.line_number}")
    print(f"Raw content: {e.raw_content}")
    print(f"Error: {e}")
```
