# API Reference

Python API documentation for programmatic use of Egregora.

## Core Pipeline

### process_whatsapp_export

Process WhatsApp export and generate blog posts.

```python
from pathlib import Path
from datetime import date
from zoneinfo import ZoneInfo
from egregora.pipeline import process_whatsapp_export

process_whatsapp_export(
    zip_path=Path("export.zip"),
    output_dir=Path("./my-blog"),
    gemini_api_key="YOUR_API_KEY",
    period="day",  # or "week", "month"
    enable_enrichment=True,
    from_date=date(2025, 1, 1),
    to_date=date(2025, 1, 31),
    timezone=ZoneInfo("America/Sao_Paulo"),
    model="models/gemini-flash-latest",
)
```

**Parameters:**
- `zip_path` (Path) - WhatsApp export ZIP file
- `output_dir` (Path) - Output directory
- `gemini_api_key` (str) - Gemini API key
- `period` (str) - "day", "week", or "month"
- `enable_enrichment` (bool) - Enable RAG/URL enrichment
- `from_date` (date | None) - Start date filter
- `to_date` (date | None) - End date filter
- `timezone` (ZoneInfo | None) - Timezone for parsing
- `model` (str | None) - Gemini model name

**Documentation:** See code in `src/egregora/pipeline.py`

## Parser

### parse_export

Parse WhatsApp export ZIP into DataFrame.

```python
from pathlib import Path
from egregora.parser import parse_export

df = parse_export(Path("export.zip"))
# Returns: Polars DataFrame with [timestamp, author, message, media]
```

**Documentation:** See code in `src/egregora/parser.py`

## Anonymizer

### anonymize_dataframe

Anonymize author names in DataFrame.

```python
import polars as pl
from egregora.anonymizer import anonymize_dataframe

df = pl.DataFrame({
    "author": ["João Silva", "Maria Santos"],
    "message": ["Hello", "Hi"]
})

anonymized_df = anonymize_dataframe(df)
# author column now contains UUIDs: ["a1b2c3d4", "e5f6g7h8"]
```

**Documentation:** `src/egregora/anonymizer.py` and [Privacy Documentation](../features/anonymization.md)

## RAG System

### VectorStore

DuckDB-based vector store for RAG.

```python
from pathlib import Path
from egregora.rag import VectorStore

store = VectorStore(Path("./rag"))

# Get all embeddings
df = store.get_all_embeddings()

# Search with embedding vector
results = store.search(embedding=[0.1, 0.2, ...], top_k=5)
```

### index_post

Index a blog post for RAG retrieval.

```python
from pathlib import Path
from google import genai
from egregora.rag import VectorStore, index_post

client = genai.Client(api_key="YOUR_KEY")
store = VectorStore(Path("./rag"))

# Index a post
num_chunks = await index_post(
    post_path=Path("posts/2025-01-15-ai-ethics.md"),
    client=client,
    store=store
)
```

### query_similar_posts

Search for similar posts.

```python
from egregora.rag import query_similar_posts

results = await query_similar_posts(
    query="What have we discussed about AI alignment?",
    client=client,
    store=store,
    top_k=5
)

for result in results:
    print(f"Post: {result['post_path']}, Score: {result['similarity']}")
```

**Documentation:** `src/egregora/rag/` and [RAG Documentation](../features/rag.md)

## Ranking System

### RankingStore

DuckDB-based ELO ranking store.

```python
from pathlib import Path
from egregora.ranking import RankingStore

store = RankingStore(Path("./rankings"))

# Initialize ratings for new posts
store.initialize_ratings(["post-1", "post-2", "post-3"])

# Get top posts
top_posts = store.get_top_posts(n=10, min_games=5)

# Get all ratings
ratings_df = store.get_all_ratings()

# Get comments for a post
comments = store.get_comments_for_post("post-1")
```

### run_comparison

Run a single ranking comparison.

```python
from pathlib import Path
from egregora.ranking.agent import run_comparison

run_comparison(
    site_dir=Path("./my-blog"),
    post_a_id="2025-01-15-ai-ethics",
    post_b_id="2025-01-16-coordination",
    profile_path=Path("profiles/a1b2c3d4.md"),
    api_key="YOUR_API_KEY",
    model="models/gemini-flash-latest"
)
```

**Documentation:** `src/egregora/ranking/` and [Ranking Documentation](../features/ranking.md)

## Editor Agent

### run_editor_session

Run LLM-powered editing session on a post.

```python
from pathlib import Path
from google import genai
from egregora.editor_agent import run_editor_session

client = genai.Client(api_key="YOUR_KEY")

result = await run_editor_session(
    post_path=Path("posts/2025-01-15-ai-ethics.md"),
    client=client,
    rag_dir=Path("./rag"),
    custom_instructions="Fix typos and improve clarity"
)

print(f"Decision: {result.decision}")  # "publish" or "hold"
print(f"Notes: {result.notes}")
print(f"Edits made: {result.edits_made}")
```

**Documentation:** `src/egregora/editor_agent.py` and [Editor Documentation](../features/editor.md)

## Profiler

### get_author_display_name

Get author's display name (alias or UUID).

```python
from pathlib import Path
from egregora.profiler import get_author_display_name

name = get_author_display_name(
    author_uuid="a1b2c3d4",
    profiles_dir=Path("./profiles")
)
# Returns: "Franklin" if alias set, else "a1b2c3d4"
```

**Documentation:** `src/egregora/profiler.py` and [Privacy Commands](../features/privacy-commands.md)

## Complete Example

```python
import asyncio
from pathlib import Path
from datetime import date
from zoneinfo import ZoneInfo
from google import genai

from egregora.pipeline import process_whatsapp_export
from egregora.ranking import RankingStore
from egregora.ranking.agent import run_comparison
from egregora.rag import VectorStore, query_similar_posts

async def main():
    # 1. Process WhatsApp export
    process_whatsapp_export(
        zip_path=Path("export.zip"),
        output_dir=Path("./my-blog"),
        gemini_api_key="YOUR_KEY",
        from_date=date(2025, 1, 1),
        to_date=date(2025, 1, 31),
        timezone=ZoneInfo("America/Sao_Paulo"),
    )

    # 2. Query RAG for similar content
    client = genai.Client(api_key="YOUR_KEY")
    store = VectorStore(Path("./my-blog/rag"))

    results = await query_similar_posts(
        query="AI alignment discussions",
        client=client,
        store=store,
        top_k=5
    )
    print(f"Found {len(results)} similar posts")

    # 3. Rank posts
    ranking_store = RankingStore(Path("./my-blog/rankings"))
    post_ids = ["2025-01-15-ai-ethics", "2025-01-16-coordination"]
    ranking_store.initialize_ratings(post_ids)

    run_comparison(
        site_dir=Path("./my-blog"),
        post_a_id=post_ids[0],
        post_b_id=post_ids[1],
        profile_path=Path("./my-blog/profiles/a1b2c3d4.md"),
        api_key="YOUR_KEY",
        model="models/gemini-flash-latest"
    )

    # 4. Get top posts
    top_posts = ranking_store.get_top_posts(n=10, min_games=3)
    print("Top posts:", top_posts)

if __name__ == "__main__":
    asyncio.run(main())
```

## Type Definitions

Key type definitions from `src/egregora/types.py`:

```python
from pathlib import Path
from datetime import datetime
from typing import TypedDict

class GroupSlug(TypedDict):
    """Group identifier."""
    slug: str

class MessageRow(TypedDict):
    """Parsed WhatsApp message."""
    timestamp: datetime
    author: str
    message: str
    media: str | None
```

## Further Reading

- Source code: `src/egregora/`
- Type hints throughout codebase
- Docstrings in key functions
- Tests: `tests/`

For high-level concepts, see [Architecture Guide](../guides/architecture.md).
