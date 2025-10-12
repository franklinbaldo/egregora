# Configuration Guide

## RAG Settings

RAG is enabled by default with smart defaults. Advanced tuning:

```python
from egregora.rag import RAGConfig

config = RAGConfig(
    top_k=3,                    # Number of historical contexts to retrieve
    min_similarity=0.70,        # Quality threshold (0-1)
    exclude_recent_days=7,      # Don't retrieve very recent posts
    chunk_size=1800,            # Tokens per chunk
    embedding_model="models/text-embedding-004",
)
```

## Profile Settings

Profiles are enabled by default with automatic prioritization:

```python
from egregora.profiles import ProfilesConfig

config = ProfilesConfig(
    max_api_calls_per_day=100,          # Daily budget
    prefer_active_participants=True,     # Update active members first
    min_messages=2,                      # Threshold for considering updates
    history_days=5,                      # Days of context for decisions
    link_members_in_posts=True,          # Auto-link mentions to profiles
    profile_base_url="/profiles/",       # URL prefix for links
)
```
