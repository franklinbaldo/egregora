# Agents Reference

Egregora uses Pydantic AI agents to generate content, enrich context, evaluate posts, and create supporting artifacts.

## Overview

Agents are AI-powered workers that transform messages and documents through various stages:

- **Writer Agent**: Generates blog posts from conversation windows
- **Reader Agent**: Evaluates and ranks posts using Elo rating system
- **Enricher Agent**: Describes URLs and media to add context
- **Profile Agent**: Creates author profiles from conversation history
- **Banner Agent**: Generates visual banners for posts
- **Avatar Agent**: Creates author avatars

All agents use the Pydantic AI framework for structured output and type safety.

## Agent Registry

The central registry for discovering and managing all available agents.

::: egregora.agents.registry
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Writer Agent

The writer agent generates blog posts from conversation windows, with support for skills, tools, and multi-turn interactions.

### Writer Agent

::: egregora.agents.writer
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Writer Context

::: egregora.agents.writer_context
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Writer Setup

::: egregora.agents.writer_setup
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Writer Helpers

::: egregora.agents.writer_helpers
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Reader Agent

The reader agent evaluates blog posts and ranks them using an Elo rating system.

### Reader Agent

::: egregora.agents.reader.agent
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Reader Models

::: egregora.agents.reader.models
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Reader Elo System

::: egregora.agents.reader.elo
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Reader Runner

::: egregora.agents.reader.reader_runner
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Enricher Agent

The enricher agent adds contextual descriptions for URLs and media files.

::: egregora.agents.enricher
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Profile Agent

The profile agent generates author profiles based on conversation history.

### Profile Generator

::: egregora.agents.profile.generator
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Profile History

::: egregora.agents.profile.history
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Profile Worker

::: egregora.agents.profile.worker
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Banner Agent

The banner agent generates visual banners for blog posts using image generation.

### Banner Agent

::: egregora.agents.banner.agent
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Banner Batch Processor

::: egregora.agents.banner.batch_processor
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Banner Image Generation

::: egregora.agents.banner.image_generation
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Banner Gemini Provider

::: egregora.agents.banner.gemini_provider
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Banner Worker

::: egregora.agents.banner.worker
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Avatar Agent

The avatar agent creates author avatars.

::: egregora.agents.avatar
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Agent Tools

Tools available to agents for extended functionality.

### Writer Tools

::: egregora.agents.tools.writer_tools
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Skill Loader

::: egregora.agents.tools.skill_loader
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Skill Injection

::: egregora.agents.tools.skill_injection
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Agent Supporting Modules

### Agent Types

::: egregora.agents.types
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Agent Models

::: egregora.agents.models
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Agent Capabilities

::: egregora.agents.capabilities
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Agent Commands

::: egregora.agents.commands
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Agent Formatting

::: egregora.agents.formatting
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Agent Taxonomy

::: egregora.agents.taxonomy
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Usage Examples

### Using the Writer Agent

```python
from egregora.agents.writer import create_writer_agent
from egregora.agents.writer_context import WriterContext

# Create context
context = WriterContext(
    messages=conversation_window,
    profiles=author_profiles,
    config=egregora_config,
)

# Create and run writer agent
agent = create_writer_agent(context)
result = await agent.run()

# Get generated post
post = result.data
print(post.content)  # Markdown blog post
```

### Using the Reader Agent

```python
from egregora.agents.reader.reader_runner import run_reader_evaluation
from pathlib import Path

# Evaluate posts and update Elo ratings
await run_reader_evaluation(
    site_root=Path("./my-blog"),
    model="gemini-2.0-flash-exp",
)

# Ratings are stored in DuckDB and displayed in site
```

### Using the Enricher Agent

```python
from egregora.agents.enricher import enrich_urls, enrich_media

# Enrich URLs in messages
enriched_docs = await enrich_urls(
    messages=message_table,
    config=egregora_config,
)

# Enrich media files
media_docs = await enrich_media(
    media_files=media_list,
    config=egregora_config,
)
```

### Using the Profile Agent

```python
from egregora.agents.profile.generator import generate_profile
from egregora.agents.profile.history import build_conversation_history

# Build conversation history for author
history = build_conversation_history(
    messages=all_messages,
    author="Alice",
)

# Generate profile
profile = await generate_profile(
    author="Alice",
    history=history,
    config=egregora_config,
)

print(profile.bio)  # Generated bio
print(profile.interests)  # Extracted interests
```

### Using the Banner Agent

```python
from egregora.agents.banner.batch_processor import generate_banners_batch

# Generate banners for multiple posts
posts = [post1, post2, post3]
banners = await generate_banners_batch(
    posts=posts,
    config=egregora_config,
)

for post, banner in zip(posts, banners):
    print(f"Banner for {post.metadata['title']}: {banner.path}")
```

## Agent Architecture

All Egregora agents follow these principles:

1. **Pydantic AI Framework**: Structured outputs with type validation
2. **Async/Await**: Non-blocking I/O for LLM calls
3. **Context Objects**: Explicit context passing (no global state)
4. **Tool Support**: Agents can use tools for extended capabilities
5. **Retry Logic**: Automatic retries with exponential backoff
6. **Caching**: Response caching to reduce API calls

## Agent Configuration

Agents are configured via the Egregora config file:

```toml
[model]
provider = "google"
name = "gemini-2.0-flash-exp"
temperature = 0.7
max_tokens = 8000

[agents.writer]
enable_skills = true
max_turns = 3

[agents.reader]
k_factor = 32
initial_rating = 1500

[agents.enricher]
enabled = true
max_urls_per_window = 5

[agents.banner]
enabled = true
style = "minimalist"
```

See the [Configuration Reference](../getting-started/configuration.md) for full details.
