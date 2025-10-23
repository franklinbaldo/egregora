# Egregora v2 Architecture

## Overview

Egregora v2 is a complete refactor using an **agent-based pipeline** architecture. The system is simple, functional, and pluggable.

## Pipeline Flow

```
WhatsApp ZIP → Parse → Filter → Curator → Enricher → Writer → Post
                                    ↓
                                Profiler → Profiles
```

## Components

### Core (`src/egregora/core/`)

- **models.py**: Core data types (Message, Topic, Post, Profile)
- **config.py**: YAML-based configuration system

### Tools (`src/egregora/tools/`)

- **registry.py**: Plugin system for tools
- **rag_tool.py**: RAG retrieval wrapper
- **privacy_tool.py**: Privacy validation wrapper

### Agents (`src/egregora/agents/`)

All agents inherit from `Agent` base class with:
- LLM client integration
- Tool registry access
- Simple memory system

#### CuratorAgent
- Filters low-quality messages
- Clusters messages into topics using LLM
- Assigns relevance scores

#### EnricherAgent
- Creates enrichment plan using LLM
- Calls tools (RAG, web, etc) for context
- Attaches context to topics

#### WriterAgent
- Generates blog post from topics
- Uses enrichment context
- Formats in markdown

#### ProfilerAgent
- Analyzes participant activity
- Generates author profiles
- Tracks topic participation

### Pipeline (`src/egregora/pipeline/`)

- **orchestrator.py**: Main pipeline coordinator
- **loader.py**: WhatsApp export loader (bridges old parser)

## Usage

```bash
python -m egregora.cli_new process \
  --zip_file=export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY \
  --enable_rag
```

## Configuration

See `config.example.yaml` for full options.

## Key Design Decisions

1. **No event sourcing** - Simple functional pipeline
2. **No backward compatibility** - Clean slate
3. **No defensive code** - Trust inputs, fail fast
4. **Agent-based** - Each stage is an autonomous agent
5. **Pluggable tools** - Easy to add new capabilities
6. **LLM-native** - Use LLM for clustering, planning, writing
