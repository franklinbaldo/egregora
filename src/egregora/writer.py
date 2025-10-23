"""Simple writer: LLM with write_post tool for editorial control."""

from pathlib import Path
import polars as pl
from google import genai
from pydantic import BaseModel
from .write_post import write_post


class PostMetadata(BaseModel):
    """Metadata schema for write_post tool."""
    title: str
    slug: str
    date: str
    tags: list[str] = []
    summary: str = ""
    authors: list[str] = []
    category: str | None = None


async def write_posts_for_period(
    df: pl.DataFrame,
    date: str,
    client: genai.Client,
    output_dir: Path = Path("output/posts"),
    model: str = "gemini-2.0-flash-exp",
) -> list[str]:
    """
    Let LLM analyze period's messages and write 0-N posts.

    The LLM has full editorial control via write_post tool:
    - Decides if content is worth writing about
    - Decides how many posts (0-N)
    - Creates all metadata (title, slug, tags, etc)

    Args:
        df: DataFrame with messages for the period (already enriched)
        date: Period identifier (e.g., "2025-01-01")
        client: Gemini client
        output_dir: Where to save posts
        model: Which LLM model to use

    Returns:
        List of file paths where posts were saved
    """

    if df.is_empty():
        return []

    markdown_table = df.write_csv(separator="|")

    prompt = f"""You are a blog editor reviewing WhatsApp group messages from {date}.

Messages (anonymized, with enriched context):
{markdown_table}

Your job:
1. Analyze these messages
2. Decide if there's anything worth writing about
3. Identify coherent topics/themes
4. Write quality blog posts

You have the write_post tool. Call it 0-N times:
- 0 times if it's all noise/spam
- 1 time for a single coherent daily summary
- Multiple times for distinct topics

For each post, provide:
- title: Engaging post title
- slug: URL-friendly slug (lowercase, hyphens)
- date: "{date}"
- tags: Relevant topic tags
- summary: 1-2 sentence summary
- authors: List of anonymized author IDs who contributed
- content: Full markdown post content

Be editorial. Only write quality content. Skip trivial conversations.
"""

    tools = [
        {
            "name": "write_post",
            "description": "Save a blog post with metadata (CMS tool)",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Markdown post content"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "slug": {"type": "string"},
                            "date": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "summary": {"type": "string"},
                            "authors": {"type": "array", "items": {"type": "string"}},
                            "category": {"type": "string"}
                        },
                        "required": ["title", "slug", "date"]
                    }
                },
                "required": ["content", "metadata"]
            }
        }
    ]

    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "tools": tools,
            "temperature": 0.7,
        }
    )

    saved_paths = []

    for part in response.candidates[0].content.parts:
        if hasattr(part, 'function_call') and part.function_call:
            if part.function_call.name == "write_post":
                args = part.function_call.args
                content = args.get("content", "")
                metadata = args.get("metadata", {})

                try:
                    path = write_post(content, metadata, output_dir)
                    saved_paths.append(path)
                except Exception as e:
                    print(f"Failed to write post: {e}")

    return saved_paths
