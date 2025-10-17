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
