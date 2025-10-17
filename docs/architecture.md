## Pipeline Overview

```mermaid
flowchart TD
    ZIP[WhatsApp ZIP exports] --> Parser[Parser.parse_multiple]
    Parser --> TranscriptCache[Transcript module\n(ensure schema, caching)]
    TranscriptCache --> UnifiedProcessor
    UnifiedProcessor -->|Anonymize| Anonymizer
    UnifiedProcessor -->|Media| MediaExtractor
    UnifiedProcessor -->|Enrichment| Enrichment[ContentEnricher]
    UnifiedProcessor -->|RAG| ChromadbRAG
    UnifiedProcessor -->|Prompts| PostGenerator
    PostGenerator --> Posts[Markdown posts]
    UnifiedProcessor --> ProfileRepo[ProfileRepository]
    ProfileRepo --> Profiles[JSON & Markdown profiles]
```

```mermaid
flowchart LR
    subgraph Processor
        A[UnifiedProcessor.process_all]
        A --> B[_collect_sources]
        A --> C[_process_source]
    end

    subgraph Support
        D[Anonymizer]
        E[MediaExtractor]
        F[ContentEnricher]
        G[ChromadbRAG]
        H[ProfileRepository]
        I[PostGenerator]
    end

    C --> D
    C --> E
    C --> F
    C --> G
    C --> H
    C --> I

    F -->|LLM| Gemini
    I -->|LLM| Gemini
    G -->|Embeddings| Gemini
```

```mermaid
classDiagram
    class UnifiedProcessor {
        +process_all()
        +estimate_api_usage()
        -_process_source()
        -_collect_sources()
    }
    class PostGenerator {
        +generate()
        -LLMInputBuilder
        -PromptLoader
    }
    class ContentEnricher {
        +enrich_dataframe()
    }
    class ProfileRepository {
        +load()
        +save()
        +iter_profiles()
        +write_index()
    }
    class ProfileStorage {
        +load()
        +save()
        +iter_profiles()
    }
    class ProfileIndexWriter {
        +write()
    }

    UnifiedProcessor --> PostGenerator
    UnifiedProcessor --> ContentEnricher
    UnifiedProcessor --> ProfileRepository
    ProfileRepository --> ProfileStorage
    ProfileRepository --> ProfileIndexWriter
```

## Alternative Pipelines for TODO Cleanup

### Split Media Extraction Stages

```mermaid
flowchart LR
    RawZIP -->|metadata only| ZIPScanner
    RawZIP -->|media only| MediaUnpacker
    ZIPScanner --> MessageParser
    MediaUnpacker --> MediaCatalog
    MessageParser --> TranscriptNormalizer
    MediaCatalog --> MediaLinker
    TranscriptNormalizer --> MediaLinker
    MediaLinker --> ProcessorCore
```

*Goal:* tackle the `MediaExtractor` TODOs by separating metadata scanning from actual media extraction, reducing branching and making unit tests easier.

### Profile Updater Service Decomposition

```mermaid
flowchart TD
    Conversations --> ParticipationCollector
    ParticipationCollector --> DecisionEngine
    DecisionEngine -->|no update| ProfileRepository
    DecisionEngine -->|update| PromptBuilder
    PromptBuilder --> LLM
    LLM --> ProfileDiffAnalyzer
    ProfileDiffAnalyzer --> MarkdownRenderer
    MarkdownRenderer --> ProfileRepository
```

*Goal:* address the monolithic `ProfileUpdater` TODOs by splitting the logic into decision, prompt building, diffing, and rendering stages.

### Streaming Enrichment & RAG Queue

```mermaid
flowchart LR
    Transcript --> ReferenceExtractor
    ReferenceExtractor --> Queue[(Enrichment Queue)]
    Queue -->|worker| EnrichmentWorker
    Queue -->|worker| RAGIndexer
    EnrichmentWorker --> EnrichmentCache
    RAGIndexer --> VectorStore
    EnrichmentCache --> ProcessorCore
    VectorStore --> ProcessorCore
```

*Goal:* break down long-running enrichment functions (`ContentEnricher`) and Chromadb indexing TODOs by offloading to background workers with explicit queues.

### Configurable Profile Prompt Pipeline

```mermaid
flowchart TD
    PromptTemplates --> PromptLoader
    PromptLoader --> PromptRegistry
    ProfileUpdater --> PromptRegistry
    LocaleSwitch --> PromptRegistry
    PromptRegistry --> LLM
```

*Goal:* remove hardcoded prompts, enabling locale-specific templates and future prompt overrides that address the TODOs in `profiles/prompts.py`.
