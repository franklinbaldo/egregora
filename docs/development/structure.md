# Project Structure

Understanding Egregora's code organization and architectural patterns.

## Three-Layer Architecture

Egregora follows a clean, three-layer architecture that separates concerns and ensures maintainability:

```
┌─────────────────────────────────────────┐
│         Orchestration Layer             │
│  (CLI, Pipeline Coordination, Config)   │
├─────────────────────────────────────────┤
│        Processing Layer                 │
│ (Privacy, Enrichment, Transformations)  │
├─────────────────────────────────────────┤
│       Input/Output Layer                │
│   (Adapters, Protocols, Serializers)    │
└─────────────────────────────────────────┘
```

### Layer Responsibilities

#### Input/Output Layer (`src/egregora/{input,output}_adapters/`)
- **Purpose**: Handle data ingress and egress
- **Responsibilities**: 
  - Parse various input formats (WhatsApp, Slack, etc.)
  - Format output in various styles (MkDocs, Hugo, JSON)
  - Define common protocols for adapters
- **Characteristics**: 
  - Protocol-driven design
  - Format-specific implementations
  - Minimal business logic

#### Processing Layer (`src/egregora/{privacy,enrichment,transformations,database}/`)
- **Purpose**: Transform and process data
- **Responsibilities**:
  - Privacy protection (PII detection and anonymization)
  - AI enrichment (topics, sentiment, entities)
  - Data transformations (functional operations)
  - Storage and retrieval
- **Characteristics**:
  - Pure functions where possible
  - Business logic concentrated here
  - Heavy use of type hints

#### Orchestration Layer (`src/egregora/{cli,orchestration}/`)
- **Purpose**: Coordinate the entire pipeline
- **Responsibilities**:
  - CLI interface
  - Pipeline execution flow
  - Configuration management
- **Characteristics**:
  - High-level coordination
  - Dependency injection
  - Error handling across layers

## Directory Structure

```
egregora/
├── src/
│   └── egregora/
│       ├── __init__.py
│       ├── cli.py                 # Command-line interface
│       ├── input_adapters/       # Input format parsers
│       │   ├── __init__.py
│       │   ├── whatsapp.py
│       │   ├── slack.py
│       │   └── protocols.py
│       ├── output_adapters/      # Output format generators
│       │   ├── __init__.py
│       │   ├── mkdocs.py
│       │   ├── hugo.py
│       │   └── protocols.py
│       ├── privacy/              # PII detection and anonymization
│       │   ├── __init__.py
│       │   ├── detector.py
│       │   ├── anonymizer.py
│       │   └── gate.py
│       ├── enrichment/           # AI-powered analysis
│       │   ├── __init__.py
│       │   ├── runners.py
│       │   ├── media.py
│       │   └── avatar.py
│       ├── agents/               # AI agents for content generation
│       │   ├── __init__.py
│       │   ├── writer.py
│       │   ├── reader.py
│       │   └── shared/           # Shared agent utilities
│       │       ├── __init__.py
│       │       ├── author_profiles.py
│       │       └── rag.py
│       ├── data_primitives/      # Core data structures
│       │   ├── __init__.py
│       │   ├── document.py
│       │   └── base_types.py
│       ├── transformations/      # Pure transformation functions
│       │   ├── __init__.py
│       │   ├── windowing.py
│       │   └── media.py
│       ├── database/             # Data storage layer
│       │   ├── __init__.py
│       │   ├── ir_schema.py
│       │   ├── duckdb_manager.py
│       │   └── views.py
│       └── orchestration/        # Pipeline coordination
│           ├── __init__.py
│           └── write_pipeline.py
├── tests/                       # Test suite
├── docs/                        # Documentation
├── scripts/                     # Utility scripts
├── pyproject.toml              # Project configuration
└── README.md
```

## Key Design Patterns

### Protocol-Based Interfaces

Input and output adapters follow protocols for consistency:

```python
from typing import Protocol

class InputAdapter(Protocol):
    def parse(self, path: str) -> list[Document]:
        ...
        
class OutputAdapter(Protocol):
    def format(self, documents: list[Document]) -> str:
        ...
```

### Functional Transformations

Data transformations are pure functions:

```python
def anonymize_content(text: str, mapping: dict[str, str]) -> str:
    """Pure function for content anonymization"""
    ...

def merge_conversations(conversations: list[Conversation]) -> Conversation:
    """Pure function for merging conversations"""
    ...
```

### Dependency Injection

Components receive dependencies rather than creating them:

```python
class Pipeline:
    def __init__(self, 
                 input_adapter: InputAdapter,
                 privacy_processor: PrivacyProcessor,
                 output_adapter: OutputAdapter):
        self.input_adapter = input_adapter
        # ...
```

## Naming Conventions

### Modules
- Use underscores: `anonymizer.py`, `write_pipeline.py`
- Descriptive names: `author_profiles.py` rather than `profiles.py`

### Classes
- PascalCase: `WriterAgent`, `PrivacyGate`
- Suffix with domain: `Anonymizer`, `Detector`

### Functions
- Use verbs for actions: `anonymize()`, `detect_pii()`, `generate_content()`
- Be descriptive: `group_by_context_window` rather than `group()`

## Type Hints

Egregora uses comprehensive type hints:

```python
from typing import Protocol, TypeAlias

DocumentId: TypeAlias = str

class ProcessingResult(Protocol):
    documents: list[Document]
    metadata: dict[str, Any]

def process_documents(
    documents: list[Document], 
    config: ProcessingConfig
) -> ProcessingResult:
    ...
```

## Error Handling

- Use specific exception types for different error cases
- Fail gracefully and provide informative error messages
- Log errors appropriately at each layer
- Isolate error handling in orchestration layer when possible